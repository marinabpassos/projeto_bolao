"""Ponto de entrada da Vercel (runtime Python). Expõe o app ASGI do FastAPI."""

import sys
from pathlib import Path

# Garante que o pacote `app` seja importável quando a Vercel executa este arquivo.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app  # noqa: E402,F401
