"""Derivação da árvore do mata-mata (funções puras, sem banco).

A estrutura vem de matches.bracket_pos: vencedores das posições 2k-1 e 2k de
uma fase alimentam a posição k da seguinte. Lado A = primeira metade.
"""

from app.phases import MATCH_STAGES

BRACKET_STAGES = ["oitavas", "quartas", "semi", "final"]
SLOTS = {"oitavas": 8, "quartas": 4, "semi": 2, "final": 1}
_PREFIX = {"quartas": "QF", "semi": "SF", "final": "FINAL"}


def side_of(stage: str, pos: int) -> str | None:
    """Lado da chave ('A'/'B'); a final não tem lado."""
    if stage == "final":
        return None
    return "A" if pos <= SLOTS[stage] // 2 else "B"


def next_slot(stage: str, pos: int) -> tuple[str, int] | None:
    """(fase, posição) que este jogo alimenta; None na final."""
    i = BRACKET_STAGES.index(stage)
    if stage == "final":
        return None
    return BRACKET_STAGES[i + 1], (pos + 1) // 2


def slot_label(stage: str, pos: int) -> str:
    """Rótulo curto do slot: QF1, SF2, FINAL."""
    prefix = _PREFIX.get(stage, stage.upper())
    return prefix if stage == "final" else f"{prefix}{pos}"


def current_stage(matches) -> str:
    """Primeira fase com jogo não-encerrado; 'final' se tudo acabou; 'grupos' sem jogos."""
    if not matches:
        return "grupos"
    for stage in MATCH_STAGES:
        if any(m.stage == stage and not m.finished for m in matches):
            return stage
    return "final"


def build_bracket(matches):
    """{fase: {pos: Match | None}} para oitavas -> final.

    Retorna None (sinal de fallback para lista) se algum jogo de mata-mata
    não tiver bracket_pos — dado antigo, nunca quebra a página.
    """
    knockout = [m for m in matches if m.stage in SLOTS]
    if any(m.bracket_pos is None for m in knockout):
        return None
    bracket = {stage: {pos: None for pos in range(1, SLOTS[stage] + 1)} for stage in BRACKET_STAGES}
    for m in knockout:
        if 1 <= m.bracket_pos <= SLOTS[m.stage]:
            bracket[m.stage][m.bracket_pos] = m
    return bracket


def _pairs(bracket, stage, side):
    """Pares consecutivos (2k-1, 2k) de um lado, com o rótulo do slot-alvo."""
    slots = bracket[stage]
    positions = [p for p in sorted(slots) if side_of(stage, p) == side]
    pairs = []
    for i in range(0, len(positions), 2):
        chunk = positions[i : i + 2]
        target = next_slot(stage, chunk[0])
        pairs.append(
            {
                "games": [(p, slots[p]) for p in chunk],
                "target": slot_label(*target) if target else None,
            }
        )
    return pairs


def jogos_view(matches, fase_param: str | None) -> dict:
    """Contexto de exibição da página de jogos (modo lista ou bracket)."""
    atual = current_stage(matches)
    sel = fase_param if fase_param in MATCH_STAGES else atual
    view = {
        "selected_stage": sel,
        "view_mode": "list",
        "bracket": None,
        "pairs_a": [],
        "pairs_b": [],
        "future_rows": [],
        "past_stages": [],
    }
    if sel not in BRACKET_STAGES:
        return view
    bracket = build_bracket(matches)
    if bracket is None:
        return view

    view["view_mode"] = "bracket"
    view["bracket"] = bracket
    view["past_stages"] = [
        s for s in MATCH_STAGES[: MATCH_STAGES.index(sel)] if any(m.stage == s for m in matches)
    ]
    if sel == "final":
        view["pairs_a"] = [{"games": [(1, bracket["final"][1])], "target": None}]
    else:
        view["pairs_a"] = _pairs(bracket, sel, "A")
        view["pairs_b"] = _pairs(bracket, sel, "B")

    # Fases além da seguinte, como linhas compactas (SF1 · A definir — 14/07).
    i = BRACKET_STAGES.index(sel)
    for stage in BRACKET_STAGES[i + 2 :]:
        for pos in range(1, SLOTS[stage] + 1):
            view["future_rows"].append(
                {"label": slot_label(stage, pos), "match": bracket[stage][pos]}
            )
    return view
