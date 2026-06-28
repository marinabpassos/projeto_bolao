"""Testes das funções de negócio em services.py."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.models import Base, Match
from app.services import seed_missing_matches


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
