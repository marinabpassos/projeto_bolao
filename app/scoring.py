"""Funções puras de pontuação do bolão.

Sem I/O e sem dependência de banco — todo o cálculo de pontos vive aqui para
ser testado isoladamente. Os routers/admin chamam estas funções e persistem o
resultado.
"""

from app.phases import (
    ARTILHEIRO_TIERS,
    BRAZIL_PROGRESS_POINTS,
    BRAZIL_YESNO_POINTS,
    progress_distance,
)

# Pontuação dos palpites de placar.
POINTS_EXACT = 10   # placar cravado
POINTS_GOALDIFF = 7  # acertou o vencedor/empate E o saldo de gols
POINTS_WINNER = 5   # acertou só o vencedor/empate
POINTS_QUALIFIER = 5  # bônus por acertar quem avançou em prorrogação/pênaltis


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


def score_match(pred_home: int, pred_away: int, real_home: int, real_away: int) -> int:
    """Pontos de um palpite de placar contra o resultado real."""
    if pred_home == real_home and pred_away == real_away:
        return POINTS_EXACT
    if (pred_home - pred_away) == (real_home - real_away):
        # Mesmo saldo de gols implica mesmo vencedor/empate.
        return POINTS_GOALDIFF
    if _sign(pred_home - pred_away) == _sign(real_home - real_away):
        return POINTS_WINNER
    return 0


def score_knockout_match(
    pred_home: int,
    pred_away: int,
    qualifier_pred: str | None,
    real_home: int,
    real_away: int,
    who_advanced: str | None,
) -> int:
    """Pontos de um palpite de mata-mata: placar dos 90 min + bônus de qualificador.

    Bônus de +5 pts: somente quando TANTO o palpite QUANTO o resultado real
    foram empate nos 90 min E o qualificador previsto bate com quem avançou.
    """
    base = score_match(pred_home, pred_away, real_home, real_away)
    pred_draw = pred_home == pred_away
    real_draw = real_home == real_away
    if pred_draw and real_draw and qualifier_pred and who_advanced:
        if qualifier_pred == who_advanced:
            base += POINTS_QUALIFIER
    return base


def tier_for_phase(stage: str) -> int:
    """Valor da faixa do artilheiro para a fase informada (KeyError se inválida)."""
    return ARTILHEIRO_TIERS[stage]


def _norm(name) -> str:
    return (name or "").strip().casefold()


def artilheiro_points(player_guess, tier_points_at_edit: int, top_scorer) -> int:
    """Pontos da aposta de artilheiro: a faixa congelada se acertou, senão 0.

    O gabarito aceita mais de um nome separado por vírgula (artilharia
    empatada); acertar qualquer um deles vale a faixa cheia.
    """
    guess = _norm(player_guess)
    scorers = {_norm(n) for n in (top_scorer or "").split(",") if _norm(n)}
    if not guess or not scorers:
        return 0
    return tier_points_at_edit if guess in scorers else 0


def brazil_yesno_points(guess_in: bool, actual_in) -> int:
    """Pontos de uma pergunta sim/não do Brasil (Neymar/Endrick)."""
    if actual_in is None:
        return 0
    return BRAZIL_YESNO_POINTS if bool(guess_in) == bool(actual_in) else 0


def brazil_progress_points(guesses_by_user: dict, actual_phase: str) -> dict:
    """Distribui os pontos da aposta 'até que fase o Brasil vai'.

    Acerto exato leva os pontos cheios. Se ninguém cravou, quem chegou mais
    próximo (menor distância de fase) leva; empates todos pontuam.
    """
    if not guesses_by_user:
        return {}
    distances = {
        user: progress_distance(guess, actual_phase)
        for user, guess in guesses_by_user.items()
    }
    best = min(distances.values())
    return {
        user: (BRAZIL_PROGRESS_POINTS if dist == best else 0)
        for user, dist in distances.items()
    }
