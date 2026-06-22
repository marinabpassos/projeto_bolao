"""Carrega a tabela de jogos (data/fixtures.json) no banco.

Uso (a partir da raiz do projeto):
    python scripts/seed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.services import seed_matches  # noqa: E402


def main() -> None:
    # Idempotente: cria as tabelas se ainda não existirem (útil no SQLite local).
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        inserted = seed_matches(db)
    if inserted:
        print(f"OK: {inserted} jogos inseridos.")
    else:
        print("Nada a fazer: já havia jogos cadastrados.")


if __name__ == "__main__":
    main()
