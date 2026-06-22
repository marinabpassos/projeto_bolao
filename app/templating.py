"""Instância compartilhada do Jinja2Templates com helpers globais."""

from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.phases import (
    ARTILHEIRO_TIERS,
    PHASES_PROGRESS,
    PHASES_PROGRESS_LABELS,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals.update(
    artilheiro_tiers=ARTILHEIRO_TIERS,
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
    "final": "Final",
}
templates.env.globals["stage_labels"] = STAGE_LABELS
