"""Leitura dos arquivos de seed (jogos e jogadores)."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_players() -> list[str]:
    path = DATA_DIR / "players.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixtures() -> list[dict]:
    path = DATA_DIR / "fixtures.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
