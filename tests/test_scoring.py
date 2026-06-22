"""Testes da lógica de pontuação do bolão (funções puras)."""

import pytest

from app.scoring import (
    score_match,
    tier_for_phase,
    artilheiro_points,
    brazil_yesno_points,
    brazil_progress_points,
)


# ---------------------------------------------------------------------------
# Palpite de placar: cravado=10, vencedor+saldo=7, só vencedor/empate=5, erro=0
# ---------------------------------------------------------------------------
class TestScoreMatch:
    def test_placar_cravado(self):
        assert score_match(2, 1, 2, 1) == 10
        assert score_match(0, 0, 0, 0) == 10

    def test_acertou_vencedor_e_saldo_mas_nao_o_placar(self):
        # palpitou 2x1 (saldo +1, casa vence), saiu 3x2 (saldo +1, casa vence)
        assert score_match(2, 1, 3, 2) == 7
        # empate com saldo 0 mas placar diferente
        assert score_match(1, 1, 2, 2) == 7

    def test_acertou_so_o_vencedor(self):
        # palpitou casa vence por 1, saiu casa vence por 2 (saldo diferente)
        assert score_match(2, 1, 3, 1) == 5
        # palpitou fora vence, saiu fora vence com outro saldo
        assert score_match(0, 1, 1, 3) == 5

    def test_acertou_o_empate_mas_saldo_sempre_zero_conta_como_cravado_ou_saldo(self):
        # empate previsto e empate real com placar diferente -> saldo igual (0) = 7
        assert score_match(0, 0, 1, 1) == 7

    def test_errou_completamente(self):
        # previu vitória da casa, saiu vitória de fora
        assert score_match(2, 0, 0, 1) == 0
        # previu empate, saiu vitória
        assert score_match(1, 1, 2, 0) == 0


# ---------------------------------------------------------------------------
# Faixas do artilheiro por fase do último palpite
# ---------------------------------------------------------------------------
class TestTierForPhase:
    def test_faixas_por_fase(self):
        assert tier_for_phase("grupos") == 60
        assert tier_for_phase("16avos") == 50
        assert tier_for_phase("oitavas") == 40
        assert tier_for_phase("quartas") == 30
        assert tier_for_phase("semi") == 20
        assert tier_for_phase("final") == 10

    def test_fase_desconhecida_levanta_erro(self):
        with pytest.raises(KeyError):
            tier_for_phase("inexistente")


class TestArtilheiroPoints:
    def test_acertou_recebe_valor_congelado(self):
        # cravou na fase de grupos (60), trocou depois? não: valor congelado é 60
        assert artilheiro_points("Mbappé", 60, "Mbappé") == 60
        # cravou já na semi (faixa 20)
        assert artilheiro_points("Haaland", 20, "Haaland") == 20

    def test_comparacao_ignora_caixa_e_espacos(self):
        assert artilheiro_points("  mbappé ", 50, "Mbappé") == 50

    def test_errou_recebe_zero(self):
        assert artilheiro_points("Messi", 60, "Mbappé") == 0

    def test_sem_palpite_ou_sem_gabarito_recebe_zero(self):
        assert artilheiro_points("", 60, "Mbappé") == 0
        assert artilheiro_points("Mbappé", 60, "") == 0
        assert artilheiro_points(None, 60, "Mbappé") == 0


# ---------------------------------------------------------------------------
# Perguntas sim/não dos jogos do Brasil (Neymar/Endrick) — 3 pts cada
# ---------------------------------------------------------------------------
class TestBrazilYesNo:
    def test_acertou(self):
        assert brazil_yesno_points(True, True) == 3
        assert brazil_yesno_points(False, False) == 3

    def test_errou(self):
        assert brazil_yesno_points(True, False) == 0
        assert brazil_yesno_points(False, True) == 0

    def test_resultado_indefinido_recebe_zero(self):
        assert brazil_yesno_points(True, None) == 0


# ---------------------------------------------------------------------------
# Aposta "até que fase o Brasil vai": exato=30; se ninguém crava, o mais próximo leva
# ---------------------------------------------------------------------------
class TestBrazilProgress:
    def test_acerto_exato_leva_pontos_cheios(self):
        guesses = {"ana": "quartas", "bia": "oitavas", "caio": "semi"}
        result = brazil_progress_points(guesses, "quartas")
        assert result == {"ana": 30, "bia": 0, "caio": 0}

    def test_varios_acertaram_exato(self):
        guesses = {"ana": "semi", "bia": "semi", "caio": "vice"}
        result = brazil_progress_points(guesses, "semi")
        assert result == {"ana": 30, "bia": 30, "caio": 0}

    def test_ninguem_acertou_mais_proximo_leva(self):
        # Brasil parou nos 'quartas'. Ninguém cravou; bia(oitavas) e caio(semi)
        # estão a 1 de distância (mais próximos) e levam; ana(grupos) a 3 não leva.
        guesses = {"ana": "grupos", "bia": "oitavas", "caio": "semi"}
        result = brazil_progress_points(guesses, "quartas")
        assert result == {"ana": 0, "bia": 30, "caio": 30}

    def test_um_unico_mais_proximo(self):
        guesses = {"ana": "campeao", "bia": "grupos"}
        # Brasil parou em 'oitavas'. ana dist=|6-2|=4, bia dist=|0-2|=2 -> bia leva
        result = brazil_progress_points(guesses, "oitavas")
        assert result == {"ana": 0, "bia": 30}

    def test_sem_palpites_retorna_vazio(self):
        assert brazil_progress_points({}, "quartas") == {}
