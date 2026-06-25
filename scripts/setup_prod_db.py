"""Cria as tabelas e carrega os jogos no banco de produção (Neon).

Lê a conexão de .env.local (escrita pela integração da Vercel) e aplica o
schema + seed. Uso (a partir da raiz do projeto):
    python scripts/setup_prod_db.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values  # noqa: E402

# Carrega a DATABASE_URL do .env.local e a injeta no ambiente ANTES de importar o app.
local = dotenv_values(ROOT / ".env.local")
db_url = local.get("DATABASE_URL")
if not db_url:
    sys.exit("DATABASE_URL não encontrada em .env.local. Rode a integração do Neon primeiro.")
os.environ["DATABASE_URL"] = db_url

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Settlement  # noqa: E402
from app.services import seed_matches  # noqa: E402

print("Conectando ao banco de produção e criando tabelas...")
Base.metadata.create_all(engine)

with SessionLocal() as db:
    if db.get(Settlement, 1) is None:
        db.add(Settlement(id=1))
        db.commit()
    inserted = seed_matches(db)

print(f"OK: tabelas criadas. Jogos inseridos: {inserted}.")
