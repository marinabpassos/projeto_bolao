"""Derivação da árvore do mata-mata e seleção de fase da página de jogos."""

from datetime import datetime

from app.bracket import (
    build_bracket,
    current_stage,
    jogos_view,
    next_slot,
    podium,
    side_of,
    slot_label,
)
from app.models import Match


def _m(stage, pos=None, finished=False, decided=True, home="X", away="Y"):
    return Match(
        stage=stage,
        round=None,
        home_team=home,
        away_team=away,
        teams_decided=decided,
        is_brazil=False,
        kickoff_at=datetime.fromisoformat("2026-07-05T20:00:00+00:00"),
        finished=finished,
        bracket_pos=pos,
    )


def _chave_completa(oitavas_finished=False):
    ms = [_m("oitavas", p, finished=oitavas_finished) for p in range(1, 9)]
    ms += [_m("quartas", p, decided=False) for p in range(1, 5)]
    ms += [_m("semi", p, decided=False) for p in range(1, 3)]
    ms += [_m("final", 1, decided=False)]
    return ms


def _finished(stage, home, away, hs, as_, adv=None, pos=None):
    m = _m(stage, pos, finished=True, home=home, away=away)
    m.home_score, m.away_score, m.who_advanced = hs, as_, adv
    return m


# ---- estrutura da árvore ---------------------------------------------------
def test_side_of():
    assert side_of("oitavas", 1) == "A"
    assert side_of("oitavas", 4) == "A"
    assert side_of("oitavas", 5) == "B"
    assert side_of("semi", 2) == "B"
    assert side_of("final", 1) is None


def test_next_slot():
    assert next_slot("oitavas", 1) == ("quartas", 1)
    assert next_slot("oitavas", 2) == ("quartas", 1)
    assert next_slot("oitavas", 8) == ("quartas", 4)
    assert next_slot("semi", 2) == ("final", 1)
    assert next_slot("final", 1) is None


def test_slot_label():
    assert slot_label("quartas", 1) == "QF1"
    assert slot_label("semi", 2) == "SF2"
    assert slot_label("final", 1) == "FINAL"


# ---- current_stage ----------------------------------------------------------
def test_current_stage_oitavas_em_andamento():
    ms = [_m("grupos", finished=True), _m("16avos", finished=True), _m("oitavas", 1)]
    assert current_stage(ms) == "oitavas"


def test_current_stage_tudo_encerrado():
    ms = [_m("final", 1, finished=True)]
    assert current_stage(ms) == "final"


def test_current_stage_sem_jogos():
    assert current_stage([]) == "grupos"


# ---- build_bracket ----------------------------------------------------------
def test_build_bracket_completo():
    br = build_bracket(_chave_completa())
    assert set(br) == {"oitavas", "quartas", "semi", "final"}
    assert br["oitavas"][3].home_team == "X"
    assert br["quartas"][4] is not None


def test_build_bracket_fallback_sem_bracket_pos():
    ms = _chave_completa()
    ms[0].bracket_pos = None  # dado antigo
    assert build_bracket(ms) is None


# ---- jogos_view ---------------------------------------------------------------
def test_jogos_view_modo_bracket_nas_oitavas():
    view = jogos_view(_chave_completa(), None)
    assert view["view_mode"] == "bracket"
    assert view["selected_stage"] == "oitavas"
    assert len(view["pairs_a"]) == 2 and len(view["pairs_b"]) == 2
    assert view["pairs_a"][0]["target"] == "QF1"
    # fases além da seguinte viram linhas compactas
    assert [r["label"] for r in view["future_rows"]] == ["SF1", "SF2", "FINAL"]


def test_jogos_view_fase_invalida_cai_na_atual():
    view = jogos_view(_chave_completa(), "banana")
    assert view["selected_stage"] == "oitavas"


def test_jogos_view_fase_lista_vira_modo_lista():
    view = jogos_view(_chave_completa(), "grupos")
    assert view["view_mode"] == "list"


def test_jogos_view_fallback_para_lista_sem_bracket_pos():
    ms = _chave_completa()
    ms[0].bracket_pos = None
    view = jogos_view(ms, None)
    assert view["view_mode"] == "list"


def test_jogos_view_past_stages():
    ms = [_m("grupos", finished=True), _m("16avos", finished=True)] + _chave_completa()
    view = jogos_view(ms, None)
    assert view["past_stages"] == ["grupos", "16avos"]


def test_jogos_view_na_final_mostra_final_e_terceiro():
    ms = _chave_completa(oitavas_finished=True)
    for m in ms:
        if m.stage != "final":
            m.finished = True
        m.teams_decided = True
    ms.append(_m("terceiro"))
    view = jogos_view(ms, None)
    assert view["selected_stage"] == "final"
    assert view["view_mode"] == "bracket"
    assert view["pairs_a"] == [] and view["pairs_b"] == []
    assert view["final_match"] is not None
    assert view["terceiro_match"].stage == "terceiro"
    assert view["podium"] == {1: None, 2: None, 3: None, 4: None}
    assert "terceiro" not in view["past_stages"]


def test_jogos_view_fase_terceiro_cai_na_visao_final():
    ms = _chave_completa() + [_m("terceiro")]
    view = jogos_view(ms, "terceiro")
    assert view["selected_stage"] == "final"


def test_jogos_view_sem_jogo_de_terceiro_nao_quebra():
    view = jogos_view(_chave_completa(), "final")
    assert view["terceiro_match"] is None
    assert view["final_match"] is not None


# ---- podium ------------------------------------------------------------------
def test_podium_vazio_sem_jogos_encerrados():
    ms = [_m("final", 1, decided=False), _m("terceiro", decided=False)]
    assert podium(ms) == {1: None, 2: None, 3: None, 4: None}


def test_podium_so_terceiro_encerrado():
    ms = [_m("final", 1), _finished("terceiro", "Brasil", "Inglaterra", 1, 1, adv="home")]
    assert podium(ms) == {1: None, 2: None, 3: "Brasil", 4: "Inglaterra"}


def test_podium_completo_sem_who_advanced_usa_placar():
    ms = [
        _finished("final", "França", "Argentina", 0, 2, pos=1),
        _finished("terceiro", "Brasil", "Inglaterra", 3, 1),
    ]
    assert podium(ms) == {1: "Argentina", 2: "França", 3: "Brasil", 4: "Inglaterra"}


def test_podium_empate_sem_who_advanced_fica_indefinido():
    ms = [_finished("final", "França", "Argentina", 1, 1, pos=1)]
    assert podium(ms) == {1: None, 2: None, 3: None, 4: None}
