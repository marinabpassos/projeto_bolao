"""Importa a tabela de jogos de uma API gratuita UMA vez (modelo misto).

Por padrão usa a football-data.org (plano free exige uma chave gratuita):
    1. Crie uma conta em https://www.football-data.org/ e copie o token.
    2. Rode (a partir da raiz do projeto):
       FOOTBALL_DATA_TOKEN=seu_token python scripts/import_fixtures.py
    3. Confira/edite data/fixtures.json (mantém só a 3ª rodada de grupos em diante)
       e depois rode `python scripts/seed.py`.

Os PLACARES reais continuam sendo lançados manualmente na área de admin — este
script só traz a tabela de confrontos/datas.

Observação: a cobertura da Copa do Mundo no plano free pode variar. Se a API não
retornar os jogos, edite data/fixtures.json manualmente (o formato está documentado
no README).
"""

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
OUT = ROOT / "app" / "data" / "fixtures.json"

# Código da competição "FIFA World Cup" na football-data.org.
COMPETITION = os.environ.get("FOOTBALL_DATA_COMP", "WC")
TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "")

STAGE_MAP = {
    "GROUP_STAGE": "grupos",
    "LAST_32": "16avos",
    "LAST_16": "oitavas",
    "QUARTER_FINALS": "quartas",
    "SEMI_FINALS": "semi",
    "FINAL": "final",
}


def main() -> None:
    if not TOKEN:
        sys.exit("Defina FOOTBALL_DATA_TOKEN com seu token gratuito da football-data.org.")

    resp = httpx.get(
        f"https://api.football-data.org/v4/competitions/{COMPETITION}/matches",
        headers={"X-Auth-Token": TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    matches = resp.json().get("matches", [])

    fixtures = []
    for m in matches:
        stage = STAGE_MAP.get(m.get("stage", ""))
        if stage is None:
            continue
        matchday = m.get("matchday")
        # O bolão começa na 3ª rodada da fase de grupos.
        if stage == "grupos" and (matchday or 0) < 3:
            continue
        home = (m.get("homeTeam") or {}).get("name") or "A definir"
        away = (m.get("awayTeam") or {}).get("name") or "A definir"
        decided = "A definir" not in (home, away)
        fixtures.append(
            {
                "stage": stage,
                "round": matchday if stage == "grupos" else None,
                "home_team": home,
                "away_team": away,
                "teams_decided": decided,
                "is_brazil": "brazil" in (home + away).casefold() or "brasil" in (home + away).casefold(),
                "kickoff_at": m.get("utcDate"),
            }
        )

    OUT.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"OK: {len(fixtures)} jogos escritos em {OUT}.\n"
        "Agora rode: python scripts/build_assets.py (para embutir) e depois "
        "python scripts/seed.py."
    )


if __name__ == "__main__":
    main()
