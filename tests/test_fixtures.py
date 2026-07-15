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


def test_terceiro_lugar_presente_e_fora_da_chave():
    terceiros = [f for f in FIXTURES if f["stage"] == "terceiro"]
    assert len(terceiros) == 1
    assert terceiros[0]["teams_decided"] is False
    assert terceiros[0]["bracket_pos"] is None


def test_stage_map_da_api_cobre_o_terceiro_lugar():
    from app.phases import MATCH_STAGES
    from app.services import _STAGE_MAP_API

    assert _STAGE_MAP_API["THIRD_PLACE"] == "terceiro"
    assert set(_STAGE_MAP_API.values()) <= set(MATCH_STAGES)
