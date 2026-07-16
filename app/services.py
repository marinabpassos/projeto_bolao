"""Regras de negócio compartilhadas: abertura de palpites, recálculo e ranking."""

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import scoring
from app.data_loader import load_fixtures
from app.models import (
    ArtilheiroPrediction,
    BrazilMatchPrediction,
    BrazilProgressPrediction,
    Match,
    Prediction,
    Settlement,
    User,
)
from app.phases import ARTILHEIRO_TIERS


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def seed_matches(db: Session) -> int:
    """Insere os jogos de data/fixtures.json se a tabela estiver vazia. Retorna quantos inseriu."""
    if db.scalar(select(func.count()).select_from(Match)):
        return 0
    count = 0
    for f in load_fixtures():
        db.add(
            Match(
                stage=f["stage"],
                round=f.get("round"),
                home_team=f["home_team"],
                away_team=f["away_team"],
                teams_decided=f.get("teams_decided", True),
                is_brazil=f.get("is_brazil", False),
                kickoff_at=datetime.fromisoformat(f["kickoff_at"]),
                bracket_pos=f.get("bracket_pos"),
            )
        )
        count += 1
    db.commit()
    return count


def seed_missing_matches(db: Session) -> int:
    """Insere jogos de fixtures.json ainda ausentes no banco.

    Dedup por (stage, kickoff_at) — mas isso não basta: sync_fixtures_from_api
    reescreve o kickoff_at de um placeholder com o horário real da API, então o
    kickoff "chutado" do fixtures.json não bate mais com o do banco. Para não
    reinserir um placeholder "A definir" duplicado nesse caso, também dedup por
    (stage, bracket_pos) quando o fixture tem bracket_pos, e por contagem de
    jogos já existentes na fase quando não tem (caso do "terceiro").
    """
    existing: set[tuple[str, datetime]] = set()
    existing_pos: set[tuple[str, int]] = set()
    stage_counts: Counter[str] = Counter()
    for m in db.scalars(select(Match)):
        kt = m.kickoff_at if m.kickoff_at.tzinfo else m.kickoff_at.replace(tzinfo=timezone.utc)
        existing.add((m.stage, kt))
        if m.bracket_pos is not None:
            existing_pos.add((m.stage, m.bracket_pos))
        stage_counts[m.stage] += 1

    fixtures = load_fixtures()
    fixture_stage_counts = Counter(f["stage"] for f in fixtures)

    count = 0
    for f in fixtures:
        kt = datetime.fromisoformat(f["kickoff_at"])
        if kt.tzinfo is None:
            kt = kt.replace(tzinfo=timezone.utc)
        if (f["stage"], kt) in existing:
            continue
        if f.get("bracket_pos") is not None and (f["stage"], f["bracket_pos"]) in existing_pos:
            continue
        if (
            f.get("bracket_pos") is None
            and f["stage"] != "grupos"
            and stage_counts[f["stage"]] >= fixture_stage_counts[f["stage"]]
        ):
            continue
        db.add(
            Match(
                stage=f["stage"],
                round=f.get("round"),
                home_team=f["home_team"],
                away_team=f["away_team"],
                teams_decided=f.get("teams_decided", True),
                is_brazil=f.get("is_brazil", False),
                kickoff_at=kt,
                bracket_pos=f.get("bracket_pos"),
            )
        )
        count += 1
    db.commit()
    return count


def _aware(dt: datetime) -> datetime:
    """Garante datetime com timezone (assume UTC se vier ingênuo do banco)."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def match_is_open(match: Match, now: datetime | None = None) -> bool:
    """Palpite de um jogo abre quando os times estão definidos e ainda não começou."""
    now = now or now_utc()
    return match.teams_decided and now < _aware(match.kickoff_at)


def current_artilheiro_phase(db: Session, now: datetime | None = None) -> str:
    """Fase atual do torneio (stage do próximo jogo a acontecer)."""
    now = now or now_utc()
    next_match = db.scalar(
        select(Match).where(Match.kickoff_at > now).order_by(Match.kickoff_at).limit(1)
    )
    return next_match.stage if next_match else "final"


def current_artilheiro_tier(db: Session, now: datetime | None = None) -> int:
    return ARTILHEIRO_TIERS[current_artilheiro_phase(db, now)]


def brazil_progress_deadline(db: Session) -> datetime | None:
    """Fecha no apito do primeiro jogo do Brasil nos 16 avos de final."""
    dt = db.scalar(
        select(func.min(Match.kickoff_at)).where(
            Match.is_brazil == True,  # noqa: E712
            Match.stage == "16avos",
        )
    )
    return _aware(dt) if dt else None


def brazil_progress_is_open(db: Session, now: datetime | None = None) -> bool:
    now = now or now_utc()
    deadline = brazil_progress_deadline(db)
    return deadline is None or now < deadline


# --------------------------------------------------------------------------- #
# Recálculo de pontos                                                          #
# --------------------------------------------------------------------------- #
def recompute_match(db: Session, match: Match) -> None:
    """Recalcula os pontos de um jogo (placar + perguntas do Brasil)."""
    if not match.finished or match.home_score is None or match.away_score is None:
        return
    is_knockout = match.stage != "grupos"
    for pred in db.scalars(select(Prediction).where(Prediction.match_id == match.id)):
        if is_knockout:
            pred.points = scoring.score_knockout_match(
                pred.home_pred, pred.away_pred, pred.qualifier_pred,
                match.home_score, match.away_score, match.who_advanced,
            )
        else:
            pred.points = scoring.score_match(
                pred.home_pred, pred.away_pred, match.home_score, match.away_score
            )
    if match.is_brazil:
        for bp in db.scalars(
            select(BrazilMatchPrediction).where(BrazilMatchPrediction.match_id == match.id)
        ):
            bp.points = scoring.brazil_yesno_points(
                bp.neymar_in, match.neymar_played
            ) + scoring.brazil_yesno_points(bp.endrick_in, match.endrick_played)
    db.commit()


def recompute_specials(db: Session) -> None:
    """Recalcula artilheiro e progresso do Brasil a partir dos gabaritos."""
    settle = db.get(Settlement, 1)
    if settle is None:
        return

    for ap in db.scalars(select(ArtilheiroPrediction)):
        ap.points = scoring.artilheiro_points(
            ap.player, ap.tier_points_at_edit, settle.top_scorer
        )

    if settle.brazil_final_phase:
        guesses = {
            bpp.user_id: bpp.phase_choice
            for bpp in db.scalars(select(BrazilProgressPrediction))
        }
        awarded = scoring.brazil_progress_points(guesses, settle.brazil_final_phase)
        for bpp in db.scalars(select(BrazilProgressPrediction)):
            bpp.points = awarded.get(bpp.user_id, 0)
    db.commit()


# --------------------------------------------------------------------------- #
# Ranking                                                                      #
# --------------------------------------------------------------------------- #
def compute_ranking(db: Session) -> list[dict]:
    """Lista de participantes ordenada por pontos totais (desc)."""
    def sums(model) -> dict[int, int]:
        rows = db.execute(
            select(model.user_id, func.coalesce(func.sum(model.points), 0)).group_by(
                model.user_id
            )
        ).all()
        return {uid: int(pts) for uid, pts in rows}

    by_match = sums(Prediction)
    by_brmatch = sums(BrazilMatchPrediction)
    by_artilheiro = sums(ArtilheiroPrediction)
    by_progress = sums(BrazilProgressPrediction)

    ranking = []
    for user in db.scalars(select(User)):
        pts_jogos = by_match.get(user.id, 0)
        pts_brasil_jogo = by_brmatch.get(user.id, 0)
        pts_artilheiro = by_artilheiro.get(user.id, 0)
        pts_progresso = by_progress.get(user.id, 0)
        ranking.append({
            "user": user,
            "total": pts_jogos + pts_brasil_jogo + pts_artilheiro + pts_progresso,
            "pts_jogos": pts_jogos,
            "pts_brasil_jogo": pts_brasil_jogo,
            "pts_artilheiro": pts_artilheiro,
            "pts_progresso": pts_progresso,
        })
    ranking.sort(key=lambda r: (-r["total"], r["user"].name.casefold()))
    return ranking


def sync_fixtures(db: Session) -> dict:
    """Sincroniza fixtures do banco: adiciona jogos reais e remove placeholders da mesma fase."""
    fixtures = load_fixtures()

    real_by_stage: dict[str, list[dict]] = {}
    for f in fixtures:
        if f.get("teams_decided", True) and f["home_team"] != "A definir":
            real_by_stage.setdefault(f["stage"], []).append(f)

    existing: dict[tuple, Match] = {}
    for m in db.scalars(select(Match)):
        kt = m.kickoff_at if m.kickoff_at.tzinfo else m.kickoff_at.replace(tzinfo=timezone.utc)
        existing[(m.stage, kt)] = m

    added = removed = 0
    for stage, stage_fixtures in real_by_stage.items():
        for p in db.scalars(
            select(Match).where(
                Match.stage == stage,
                Match.teams_decided == False,  # noqa: E712
                Match.home_team == "A definir",
            )
        ):
            db.delete(p)
            removed += 1

        for f in stage_fixtures:
            kt = datetime.fromisoformat(f["kickoff_at"])
            if kt.tzinfo is None:
                kt = kt.replace(tzinfo=timezone.utc)
            if (f["stage"], kt) not in existing:
                db.add(
                    Match(
                        stage=f["stage"],
                        round=f.get("round"),
                        home_team=f["home_team"],
                        away_team=f["away_team"],
                        teams_decided=f.get("teams_decided", True),
                        is_brazil=f.get("is_brazil", False),
                        kickoff_at=kt,
                        bracket_pos=f.get("bracket_pos"),
                    )
                )
                added += 1

    # Backfill de bracket_pos em jogos já existentes (nunca sobrescreve valor definido).
    for f in fixtures:
        pos = f.get("bracket_pos")
        if pos is None:
            continue
        kt = datetime.fromisoformat(f["kickoff_at"])
        if kt.tzinfo is None:
            kt = kt.replace(tzinfo=timezone.utc)
        m = existing.get((f["stage"], kt))
        if m is not None and m.bracket_pos is None:
            m.bracket_pos = pos

    db.commit()
    return {"added": added, "removed": removed}


# --------------------------------------------------------------------------- #
# Sincronização de resultados via football-data.org                            #
# --------------------------------------------------------------------------- #
_STAGE_MAP_API = {
    "GROUP_STAGE": "grupos",
    "LAST_32": "16avos",
    "LAST_16": "oitavas",
    "QUARTER_FINALS": "quartas",
    "SEMI_FINALS": "semi",
    "THIRD_PLACE": "terceiro",
    "FINAL": "final",
}

# A football-data.org devolve os nomes em inglês; o app usa português em todo lugar
# (bandeiras em app/flags.py, detecção de Brasil). Traduz na fronteira da API.
_TEAM_NAME_PT = {
    "Algeria": "Argélia",
    "Argentina": "Argentina",
    "Australia": "Austrália",
    "Austria": "Áustria",
    "Belgium": "Bélgica",
    "Bosnia-Herzegovina": "Bósnia e Herzegovina",
    "Brazil": "Brasil",
    "Canada": "Canadá",
    "Cape Verde Islands": "Cabo Verde",
    "Colombia": "Colômbia",
    "Congo DR": "RD Congo",
    "Croatia": "Croácia",
    "Curaçao": "Curaçao",
    "Czechia": "Tchéquia",
    "Ecuador": "Equador",
    "Egypt": "Egito",
    "England": "Inglaterra",
    "France": "França",
    "Germany": "Alemanha",
    "Ghana": "Gana",
    "Haiti": "Haiti",
    "Iran": "Irã",
    "Iraq": "Iraque",
    "Ivory Coast": "Costa do Marfim",
    "Japan": "Japão",
    "Jordan": "Jordânia",
    "Mexico": "México",
    "Morocco": "Marrocos",
    "Netherlands": "Países Baixos",
    "New Zealand": "Nova Zelândia",
    "Norway": "Noruega",
    "Panama": "Panamá",
    "Paraguay": "Paraguai",
    "Portugal": "Portugal",
    "Qatar": "Catar",
    "Saudi Arabia": "Arábia Saudita",
    "Scotland": "Escócia",
    "Senegal": "Senegal",
    "South Africa": "África do Sul",
    "South Korea": "Coreia do Sul",
    "Spain": "Espanha",
    "Sweden": "Suécia",
    "Switzerland": "Suíça",
    "Tunisia": "Tunísia",
    "Turkey": "Turquia",
    "United States": "Estados Unidos",
    "Uruguay": "Uruguai",
    "Uzbekistan": "Uzbequistão",
}


def _team_pt(name: str) -> str:
    """Nome da seleção em português (fallback: o próprio nome se não estiver no mapa)."""
    return _TEAM_NAME_PT.get(name, name)


def _fetch_wc_matches(token: str, status: str | None = None) -> list[dict]:
    """Busca jogos da Copa do Mundo na football-data.org (opcionalmente filtrando por status)."""
    import httpx  # import local para não pesar no bundle serverless

    params = {"status": status} if status else {}
    resp = httpx.get(
        "https://api.football-data.org/v4/competitions/WC/matches",
        params=params,
        headers={"X-Auth-Token": token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("matches", [])


def sync_fixtures_from_api(db: Session, token: str) -> int:
    """Preenche os confrontos do mata-mata a partir dos jogos já definidos na football-data.org.

    Retorna quantos placeholders ("A definir") foram preenchidos.
    Casa por (fase, ordem cronológica): para cada fase, os placeholders locais e os jogos
    da API com os dois times definidos são ordenados por horário e emparelhados na ordem —
    mantendo o alinhamento com `bracket_pos` (que no seed segue a ordem cronológica).
    Só toca em placeholders (teams_decided=False / "A definir"); jogos já preenchidos à mão
    pelo admin nunca são sobrescritos. Idempotente.
    """
    api_matches = _fetch_wc_matches(token)

    # Jogos da API com os dois times definidos, agrupados pela nossa nomenclatura de fase.
    api_by_stage: dict[str, list[dict]] = {}
    for m in api_matches:
        stage = _STAGE_MAP_API.get(m.get("stage", ""))
        if stage is None or stage == "grupos":
            continue
        home = (m.get("homeTeam") or {}).get("name")
        away = (m.get("awayTeam") or {}).get("name")
        if not home or not away:
            continue
        api_by_stage.setdefault(stage, []).append(m)

    count = 0
    for stage, matches in api_by_stage.items():
        placeholders = list(
            db.scalars(
                select(Match)
                .where(
                    Match.stage == stage,
                    Match.teams_decided == False,  # noqa: E712
                    Match.home_team == "A definir",
                )
                .order_by(Match.kickoff_at)
            )
        )
        if not placeholders:
            continue

        matches_sorted = sorted(matches, key=lambda m: m["utcDate"])
        for local, api in zip(placeholders, matches_sorted):
            home = _team_pt(api["homeTeam"]["name"])
            away = _team_pt(api["awayTeam"]["name"])
            local.home_team = home
            local.away_team = away
            local.teams_decided = True
            local.is_brazil = "brasil" in (home + away).casefold()
            local.kickoff_at = datetime.fromisoformat(api["utcDate"].replace("Z", "+00:00"))
            count += 1

    db.commit()
    return count


def sync_results_from_api(db: Session, token: str) -> int:
    """Busca resultados finalizados na football-data.org e atualiza o banco.

    Retorna o número de jogos atualizados.
    Não re-processa jogos já marcados como finished.
    Correspondência por (stage, kickoff_at) com tolerância de ±5 minutos.
    """
    count = 0
    for m in _fetch_wc_matches(token, status="FINISHED"):
        stage = _STAGE_MAP_API.get(m.get("stage", ""))
        if not stage:
            continue

        score_block = m.get("score") or {}
        score = score_block.get("regularTime") or score_block.get("fullTime") or {}
        home_score = score.get("home")
        away_score = score.get("away")
        if home_score is None or away_score is None:
            continue

        api_kickoff = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
        window_start = api_kickoff - timedelta(minutes=5)
        window_end = api_kickoff + timedelta(minutes=5)

        local = db.scalar(
            select(Match).where(
                Match.stage == stage,
                Match.kickoff_at >= window_start,
                Match.kickoff_at <= window_end,
            )
        )
        if local is None or local.finished:
            continue

        local.home_score = home_score
        local.away_score = away_score
        local.finished = True
        # Determinar quem avançou a partir do campo "winner" da API
        winner = (m.get("score") or {}).get("winner")  # "HOME_TEAM" | "AWAY_TEAM" | null
        if local.stage != "grupos" and winner:
            local.who_advanced = "home" if winner == "HOME_TEAM" else "away"
        db.commit()
        recompute_match(db, local)
        count += 1

    return count
