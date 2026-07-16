"""Instância compartilhada do Jinja2Templates com helpers globais.

Os templates são carregados de `app/templates_data.py` (embutidos em Python) via
DictLoader, para que o bundle serverless da Vercel não dependa de includeFiles.
"""

from datetime import timezone
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates
from jinja2 import DictLoader, Environment, select_autoescape

from app.config import get_settings
from app.flags import flag_url
from app.phases import (
    ARTILHEIRO_TIERS,
    PHASES_PROGRESS,
    PHASES_PROGRESS_LABELS,
)
from app.templates_data import TEMPLATES

_env = Environment(
    loader=DictLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "xml"]),
)
templates = Jinja2Templates(env=_env)
templates.env.globals.update(
    artilheiro_tiers=ARTILHEIRO_TIERS,
    flag_url=flag_url,
    phases_progress=PHASES_PROGRESS,
    phases_progress_labels=PHASES_PROGRESS_LABELS,
    dev_login=get_settings().dev_login,
)

_BRT = ZoneInfo("America/Sao_Paulo")


def dt_br(value) -> str:
    """Formata um datetime no horário de Brasília."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_BRT).strftime("%d/%m %H:%M")


templates.env.filters["dt_br"] = dt_br

STAGE_LABELS = {
    "grupos": "Fase de grupos",
    "16avos": "16-avos de final",
    "oitavas": "Oitavas de final",
    "quartas": "Quartas de final",
    "semi": "Semifinal",
    "terceiro": "Disputa de 3º lugar",
    "final": "Final",
}
templates.env.globals["stage_labels"] = STAGE_LABELS
