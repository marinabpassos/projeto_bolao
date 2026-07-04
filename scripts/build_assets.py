"""Regenera os módulos Python embutidos a partir das fontes.

Embutimos os templates e os dados em Python (app/templates_data.py e
app/seed_data.py) para que o bundle serverless da Vercel os inclua sem depender
de `includeFiles`. Rode este script após editar os arquivos-fonte:

    python scripts/build_assets.py

Fontes:
  - Templates HTML: app/templates/*.html  -> app/templates_data.py
  - Dados (jogos/jogadores): app/data/*.json -> app/seed_data.py
"""

import json
import pprint
from pathlib import Path

ROOT = Path(__file__).parent.parent
APP = ROOT / "app"

TEMPLATE_NAMES = [
    "base.html",
    "jogos.html",
    "_match_card.html",
    "apostas.html",
    "ranking.html",
    "regras.html",
    "admin.html",
]


def build_templates() -> None:
    tdir = APP / "templates"
    out = APP / "templates_data.py"
    with out.open("w", encoding="utf-8") as f:
        f.write('"""Templates HTML embutidos (gerados de app/templates/*.html).\n\n')
        f.write("NÃO edite à mão — rode scripts/build_assets.py após mudar os .html.\n")
        f.write('Embutidos para o bundle serverless da Vercel (sem includeFiles).\n"""\n\n')
        f.write("TEMPLATES = {\n")
        for n in TEMPLATE_NAMES:
            f.write(f"    {n!r}: {(tdir / n).read_text(encoding='utf-8')!r},\n")
        f.write("}\n")
    print(f"OK templates_data.py ({out.stat().st_size} bytes, {len(TEMPLATE_NAMES)} templates)")


def build_seed_data() -> None:
    ddir = APP / "data"
    players = json.loads((ddir / "players.json").read_text(encoding="utf-8"))
    fixtures = json.loads((ddir / "fixtures.json").read_text(encoding="utf-8"))
    out = APP / "seed_data.py"
    with out.open("w", encoding="utf-8") as f:
        f.write('"""Dados de seed embutidos (gerados de app/data/*.json).\n\n')
        f.write("NÃO edite à mão — rode scripts/build_assets.py após mudar os .json.\n")
        f.write('Embutidos para o bundle serverless da Vercel (sem includeFiles).\n"""\n\n')
        f.write("PLAYERS = " + pprint.pformat(players, width=100, sort_dicts=False) + "\n\n")
        f.write("FIXTURES = " + pprint.pformat(fixtures, width=120, sort_dicts=False) + "\n")
    print(f"OK seed_data.py ({out.stat().st_size} bytes, {len(fixtures)} jogos)")


if __name__ == "__main__":
    build_templates()
    build_seed_data()
