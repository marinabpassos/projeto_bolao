"""Sanidade dos fixtures embutidos: estrutura da chave oitavas -> final."""

from collections import Counter

from app.seed_data import FIXTURES

BRACKET_SLOTS = {"oitavas": 8, "quartas": 4, "semi": 2, "final": 1}


def _knockout():
    return [f for f in FIXTURES if f["stage"] in BRACKET_SLOTS]


def test_todo_jogo_de_mata_mata_tem_bracket_pos():
    faltando = [f for f in _knockout() if f.get("bracket_pos") is None]
    assert faltando == []


def test_quantidade_de_jogos_por_fase():
    contagem = Counter(f["stage"] for f in _knockout())
    assert contagem == Counter(BRACKET_SLOTS)


def test_posicoes_unicas_e_dentro_da_faixa():
    for stage, slots in BRACKET_SLOTS.items():
        posicoes = sorted(f["bracket_pos"] for f in _knockout() if f["stage"] == stage)
        assert posicoes == list(range(1, slots + 1)), stage
