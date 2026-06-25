"""Regras de negócio compartilhadas: abertura de palpites, recálculo e ranking."""

from datetime import datetime, timezone

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
    """Fecha no apito do primeiro jogo do Brasil com times definidos."""
    dt = db.scalar(
        select(func.min(Match.kickoff_at)).where(
            Match.is_brazil == True, Match.teams_decided == True  # noqa: E712
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
    for pred in db.scalars(select(Prediction).where(Prediction.match_id == match.id)):
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
