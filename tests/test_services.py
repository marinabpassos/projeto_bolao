"""Testes das funções de negócio em services.py."""

from datetime import datetime, timezone

import httpx
import pytest
import respx
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.models import Base, Match
from app.services import (
    seed_missing_matches,
    sync_fixtures,
    sync_fixtures_from_api,
    sync_results_from_api,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _match(stage: str, kickoff: str, home: str = "A definir", away: str = "A definir") -> Match:
    return Match(
        stage=stage,
        round=None,
        home_team=home,
        away_team=away,
        teams_decided=False,
        is_brazil=False,
        kickoff_at=datetime.fromisoformat(kickoff),
        finished=False,
    )


FAKE_FIXTURES = [
    {
        "stage": "16avos",
        "round": None,
        "home_team": "A definir",
        "away_team": "A definir",
        "teams_decided": False,
        "is_brazil": False,
        "kickoff_at": "2026-06-29T19:00:00+00:00",
    },
    {
        "stage": "16avos",
        "round": None,
        "home_team": "A definir",
        "away_team": "A definir",
        "teams_decided": False,
        "is_brazil": False,
        "kickoff_at": "2026-06-30T19:00:00+00:00",
    },
    {
        "stage": "16avos",
        "round": None,
        "home_team": "A definir",
        "away_team": "A definir",
        "teams_decided": False,
        "is_brazil": False,
        "kickoff_at": "2026-07-01T18:00:00+00:00",
    },
]


class TestSeedMissingMatches:
    def test_insere_todos_quando_banco_vazio(self, db, monkeypatch):
        monkeypatch.setattr("app.services.load_fixtures", lambda: FAKE_FIXTURES)
        count = seed_missing_matches(db)
        assert count == 3
        total = db.scalar(select(func.count()).select_from(Match))
        assert total == 3

    def test_nao_duplica_jogos_ja_existentes(self, db, monkeypatch):
        monkeypatch.setattr("app.services.load_fixtures", lambda: FAKE_FIXTURES)
        # Jogo de June 29 já está no banco
        db.add(_match("16avos", "2026-06-29T19:00:00+00:00"))
        db.commit()

        count = seed_missing_matches(db)
        assert count == 2  # só os dois novos
        total = db.scalar(select(func.count()).select_from(Match))
        assert total == 3

    def test_idempotente_segunda_chamada_retorna_zero(self, db, monkeypatch):
        monkeypatch.setattr("app.services.load_fixtures", lambda: FAKE_FIXTURES)
        seed_missing_matches(db)
        count2 = seed_missing_matches(db)
        assert count2 == 0
        assert db.scalar(select(func.count()).select_from(Match)) == 3

    def test_nao_duplica_mata_mata_quando_api_reescreveu_kickoff(self, db, monkeypatch):
        # sync_fixtures_from_api reescreve o kickoff_at do placeholder com o horário
        # real da API. O fixture ainda tem o horário "chutado" original, mas o
        # (stage, bracket_pos) já existe no banco — não deve reinserir.
        fixtures = [
            {
                "stage": "quartas",
                "round": None,
                "home_team": "A definir",
                "away_team": "A definir",
                "teams_decided": False,
                "is_brazil": False,
                "kickoff_at": "2026-07-10T12:00:00+00:00",  # horário chutado
                "bracket_pos": 1,
            }
        ]
        monkeypatch.setattr("app.services.load_fixtures", lambda: fixtures)
        m = _match("quartas", "2026-07-10T19:00:00+00:00", "Brasil", "Argentina")  # horário real
        m.teams_decided = True
        m.bracket_pos = 1
        db.add(m)
        db.commit()

        count = seed_missing_matches(db)

        assert count == 0
        total = db.scalar(select(func.count()).select_from(Match))
        assert total == 1

    def test_nao_duplica_terceiro_quando_api_reescreveu_kickoff(self, db, monkeypatch):
        # O placeholder de "terceiro" não tem bracket_pos; o dedup precisa cair no
        # fallback por contagem de jogos já existentes na fase.
        fixtures = [
            {
                "stage": "terceiro",
                "round": None,
                "home_team": "A definir",
                "away_team": "A definir",
                "teams_decided": False,
                "is_brazil": False,
                "kickoff_at": "2026-07-14T12:00:00+00:00",  # horário chutado
            }
        ]
        monkeypatch.setattr("app.services.load_fixtures", lambda: fixtures)
        m = _match("terceiro", "2026-07-14T19:00:00+00:00", "Brasil", "Argentina")  # horário real
        m.teams_decided = True
        db.add(m)
        db.commit()

        count = seed_missing_matches(db)

        assert count == 0
        total = db.scalar(select(func.count()).select_from(Match))
        assert total == 1

    def test_insere_terceiro_quando_banco_nao_tem_nenhum(self, db, monkeypatch):
        fixtures = [
            {
                "stage": "terceiro",
                "round": None,
                "home_team": "A definir",
                "away_team": "A definir",
                "teams_decided": False,
                "is_brazil": False,
                "kickoff_at": "2026-07-14T12:00:00+00:00",
            }
        ]
        monkeypatch.setattr("app.services.load_fixtures", lambda: fixtures)

        count = seed_missing_matches(db)

        assert count == 1
        total = db.scalar(select(func.count()).select_from(Match))
        assert total == 1


FAKE_API_RESPONSE = {
    "matches": [
        {
            "stage": "LAST_32",
            "utcDate": "2026-06-29T19:00:00Z",
            "status": "FINISHED",
            "homeTeam": {"name": "Germany"},
            "awayTeam": {"name": "Morocco"},
            "score": {
                "fullTime": {"home": 2, "away": 1}
            },
        },
        {
            "stage": "LAST_32",
            "utcDate": "2026-06-30T19:00:00Z",
            "status": "FINISHED",
            "homeTeam": {"name": "France"},
            "awayTeam": {"name": "Japan"},
            "score": {
                "fullTime": {"home": None, "away": None}  # ainda sem placar (não deve atualizar)
            },
        },
    ]
}


class TestSyncResultsFromApi:
    def test_atualiza_jogo_finalizado(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_API_RESPONSE)
        )
        # Jogo existe no banco, ainda não finalizado
        m = _match("16avos", "2026-06-29T19:00:00+00:00", "Germany", "Morocco")
        m.teams_decided = True
        db.add(m)
        db.commit()

        count = sync_results_from_api(db, token="fake-token")

        assert count == 1
        db.refresh(m)
        assert m.finished is True
        assert m.home_score == 2
        assert m.away_score == 1

    def test_ignora_placar_nulo(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_API_RESPONSE)
        )
        m = _match("16avos", "2026-06-30T19:00:00+00:00", "France", "Japan")
        m.teams_decided = True
        db.add(m)
        db.commit()

        count = sync_results_from_api(db, token="fake-token")

        assert count == 0
        db.refresh(m)
        assert m.finished is False

    def test_nao_re_processa_jogo_ja_finalizado(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_API_RESPONSE)
        )
        m = _match("16avos", "2026-06-29T19:00:00+00:00", "Germany", "Morocco")
        m.teams_decided = True
        m.finished = True
        m.home_score = 2
        m.away_score = 1
        db.add(m)
        db.commit()

        count = sync_results_from_api(db, token="fake-token")
        assert count == 0

    def test_popula_who_advanced_nos_penaltis(self, db, respx_mock):
        response_with_winner = {
            "matches": [
                {
                    "stage": "LAST_32",
                    "utcDate": "2026-06-29T19:00:00Z",
                    "status": "FINISHED",
                    "homeTeam": {"name": "Germany"},
                    "awayTeam": {"name": "Morocco"},
                    "score": {
                        "fullTime": {"home": 1, "away": 1},
                        "winner": "HOME_TEAM",
                    },
                }
            ]
        }
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=response_with_winner)
        )
        m = _match("16avos", "2026-06-29T19:00:00+00:00", "Germany", "Morocco")
        m.teams_decided = True
        db.add(m)
        db.commit()

        sync_results_from_api(db, token="fake-token")

        db.refresh(m)
        assert m.who_advanced == "home"
        assert m.home_score == 1
        assert m.away_score == 1


# --------------------------------------------------------------------------- #
# sync_fixtures_from_api (preenche confrontos do mata-mata)                     #
# --------------------------------------------------------------------------- #
# A API devolve nomes em inglês; a sync deve traduzir para o português do app.
FAKE_QUARTAS_API = {
    "matches": [
        {
            "stage": "QUARTER_FINALS",
            "utcDate": "2026-07-10T19:00:00Z",
            "status": "SCHEDULED",
            "homeTeam": {"name": "Brazil"},
            "awayTeam": {"name": "Argentina"},
        },
        {
            "stage": "QUARTER_FINALS",
            "utcDate": "2026-07-11T19:00:00Z",
            "status": "SCHEDULED",
            "homeTeam": {"name": "France"},
            "awayTeam": {"name": "Spain"},
        },
    ]
}


def _placeholder(stage: str, kickoff: str, bracket_pos: int) -> Match:
    m = _match(stage, kickoff)
    m.bracket_pos = bracket_pos
    return m


class TestSyncFixturesFromApi:
    def test_preenche_placeholders_por_ordem(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_QUARTAS_API)
        )
        # Placeholders com horário "chutado" diferente do real da API.
        db.add(_placeholder("quartas", "2026-07-10T12:00:00+00:00", 1))
        db.add(_placeholder("quartas", "2026-07-11T12:00:00+00:00", 2))
        db.commit()

        count = sync_fixtures_from_api(db, token="fake-token")

        assert count == 2
        q1 = db.scalar(select(Match).where(Match.bracket_pos == 1, Match.stage == "quartas"))
        q2 = db.scalar(select(Match).where(Match.bracket_pos == 2, Match.stage == "quartas"))
        assert (q1.home_team, q1.away_team) == ("Brasil", "Argentina")
        assert q1.teams_decided is True
        assert q1.is_brazil is True  # detecta Brasil
        # SQLite devolve datetime ingênuo; o valor real é o horário da API (não o "chutado").
        assert q1.kickoff_at.replace(tzinfo=timezone.utc) == datetime(2026, 7, 10, 19, 0, tzinfo=timezone.utc)
        assert (q2.home_team, q2.away_team) == ("França", "Espanha")
        assert q2.is_brazil is False

    def test_ignora_jogos_sem_dois_times(self, db, respx_mock):
        response = {
            "matches": [
                {
                    "stage": "QUARTER_FINALS",
                    "utcDate": "2026-07-10T19:00:00Z",
                    "status": "SCHEDULED",
                    "homeTeam": {"name": "Brasil"},
                    "awayTeam": {"name": None},  # ainda não definido
                }
            ]
        }
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=response)
        )
        db.add(_placeholder("quartas", "2026-07-10T12:00:00+00:00", 1))
        db.commit()

        count = sync_fixtures_from_api(db, token="fake-token")

        assert count == 0
        q1 = db.scalar(select(Match).where(Match.stage == "quartas"))
        assert q1.home_team == "A definir"
        assert q1.teams_decided is False

    def test_nao_sobrescreve_jogo_preenchido_manualmente(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_QUARTAS_API)
        )
        # Admin já preencheu a primeira quarta à mão.
        manual = _match("quartas", "2026-07-10T19:00:00+00:00", "Uruguai", "Portugal")
        manual.teams_decided = True
        manual.bracket_pos = 1
        db.add(manual)
        db.add(_placeholder("quartas", "2026-07-11T12:00:00+00:00", 2))
        db.commit()

        count = sync_fixtures_from_api(db, token="fake-token")

        # Só o placeholder restante é preenchido; o manual fica intacto.
        assert count == 1
        db.refresh(manual)
        assert (manual.home_team, manual.away_team) == ("Uruguai", "Portugal")

    def test_idempotente(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_QUARTAS_API)
        )
        db.add(_placeholder("quartas", "2026-07-10T12:00:00+00:00", 1))
        db.add(_placeholder("quartas", "2026-07-11T12:00:00+00:00", 2))
        db.commit()

        sync_fixtures_from_api(db, token="fake-token")
        count2 = sync_fixtures_from_api(db, token="fake-token")

        assert count2 == 0


# --------------------------------------------------------------------------- #
# bracket_pos                                                                  #
# --------------------------------------------------------------------------- #
BRACKET_FIXTURES = [
    {
        "stage": "oitavas", "round": None, "home_team": "Brasil", "away_team": "Noruega",
        "teams_decided": True, "is_brazil": True,
        "kickoff_at": "2026-07-05T20:00:00+00:00", "bracket_pos": 3,
    },
    {
        "stage": "quartas", "round": None, "home_team": "A definir", "away_team": "A definir",
        "teams_decided": False, "is_brazil": False,
        "kickoff_at": "2026-07-10T19:00:00+00:00", "bracket_pos": 1,
    },
]


def test_seed_missing_matches_carrega_bracket_pos(db, monkeypatch):
    monkeypatch.setattr("app.services.load_fixtures", lambda: BRACKET_FIXTURES)
    seed_missing_matches(db)
    m = db.scalar(select(Match).where(Match.stage == "oitavas"))
    assert m.bracket_pos == 3


def test_sync_fixtures_backfill_bracket_pos_em_jogo_existente(db, monkeypatch):
    # Jogo já no banco SEM bracket_pos (dado antigo), mesmo (stage, kickoff) do fixture.
    db.add(_match("oitavas", "2026-07-05T20:00:00+00:00", "Brasil", "Noruega"))
    db.commit()
    monkeypatch.setattr("app.services.load_fixtures", lambda: BRACKET_FIXTURES)
    sync_fixtures(db)
    m = db.scalar(select(Match).where(Match.stage == "oitavas"))
    assert m.bracket_pos == 3


def test_sync_fixtures_nao_sobrescreve_bracket_pos(db, monkeypatch):
    existing = _match("oitavas", "2026-07-05T20:00:00+00:00", "Brasil", "Noruega")
    existing.bracket_pos = 7  # valor definido manualmente pelo admin
    db.add(existing)
    db.commit()
    monkeypatch.setattr("app.services.load_fixtures", lambda: BRACKET_FIXTURES)
    sync_fixtures(db)
    m = db.scalar(select(Match).where(Match.stage == "oitavas"))
    assert m.bracket_pos == 7
