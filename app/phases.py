"""Fases da Copa, ordenação e tabelas de pontuação (constantes puras).

Mantido separado de `config.py` (que lê variáveis de ambiente) para que a
lógica de pontuação possa ser testada sem nenhuma dependência externa.
"""

# Fases dos JOGOS (usadas em matches.stage e nas faixas do artilheiro).
# A Copa de 2026 tem 48 seleções: o mata-mata começa nos 16-avos.
MATCH_STAGES = ["grupos", "16avos", "oitavas", "quartas", "semi", "terceiro", "final"]

# Faixa de pontos do artilheiro conforme a fase do ÚLTIMO palpite.
# Quanto mais cedo (mais jogos restando), mais vale.
ARTILHEIRO_TIERS = {
    "grupos": 60,
    "16avos": 50,
    "oitavas": 40,
    "quartas": 30,
    "semi": 20,
    "terceiro": 10,  # mesma faixa da final: a essa altura restam só 2 jogos
    "final": 10,
}

# Opções da aposta "até que fase o Brasil vai" (ordenadas; distância = diferença de índice).
# 'vice' = perdeu a final; 'campeao' = ganhou a final.
PHASES_PROGRESS = ["grupos", "16avos", "oitavas", "quartas", "semi", "vice", "campeao"]

# Rótulos amigáveis para exibição.
PHASES_PROGRESS_LABELS = {
    "grupos": "Eliminado na fase de grupos",
    "16avos": "Eliminado nos 16-avos",
    "oitavas": "Eliminado nas oitavas",
    "quartas": "Eliminado nas quartas",
    "semi": "Eliminado na semifinal",
    "vice": "Vice-campeão",
    "campeao": "Campeão",
}

# Pontos da aposta de progresso do Brasil (acerto exato ou, na falta, o mais próximo).
BRAZIL_PROGRESS_POINTS = 30

# Pontos de cada pergunta sim/não dos jogos do Brasil (Neymar/Endrick).
BRAZIL_YESNO_POINTS = 3


def progress_distance(phase_a: str, phase_b: str) -> int:
    """Distância (em fases) entre duas opções de progresso do Brasil."""
    return abs(PHASES_PROGRESS.index(phase_a) - PHASES_PROGRESS.index(phase_b))
