"""Acesso aos dados de seed (jogadores e jogos).

Os dados ficam embutidos em `app/seed_data.py` para que o bundle serverless da
Vercel os inclua automaticamente (via import), sem depender de `includeFiles`.
Para atualizar a tabela, edite `app/seed_data.py` (ou regenere a partir de um
JSON com o script de import).
"""

from app.seed_data import FIXTURES, PLAYERS


def load_players() -> list[str]:
    return list(PLAYERS)


def load_fixtures() -> list[dict]:
    return list(FIXTURES)
