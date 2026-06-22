"""Apostas especiais: artilheiro, progresso do Brasil, Neymar/Endrick por jogo."""

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import (
    ArtilheiroPrediction,
    BrazilMatchPrediction,
    BrazilProgressPrediction,
    Match,
    User,
)
from app.phases import PHASES_PROGRESS
from app.services import (
    brazil_progress_is_open,
    current_artilheiro_tier,
    match_is_open,
)

router = APIRouter(prefix="/apostas", tags=["apostas"])


@router.post("/artilheiro")
def save_artilheiro(
    player: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    player = player.strip()
    if not player:
        raise HTTPException(status_code=400, detail="Escolha um jogador.")
    tier = current_artilheiro_tier(db)  # faixa congelada no momento deste palpite
    ap = db.scalar(
        select(ArtilheiroPrediction).where(ArtilheiroPrediction.user_id == user.id)
    )
    if ap is None:
        ap = ArtilheiroPrediction(user_id=user.id)
        db.add(ap)
    ap.player = player
    ap.tier_points_at_edit = tier
    db.commit()
    return RedirectResponse(url="/apostas", status_code=303)


@router.post("/brasil-progresso")
def save_brazil_progress(
    phase_choice: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if phase_choice not in PHASES_PROGRESS:
        raise HTTPException(status_code=400, detail="Opção de fase inválida.")
    if not brazil_progress_is_open(db):
        raise HTTPException(status_code=400, detail="A aposta do Brasil já está fechada.")
    bpp = db.scalar(
        select(BrazilProgressPrediction).where(BrazilProgressPrediction.user_id == user.id)
    )
    if bpp is None:
        bpp = BrazilProgressPrediction(user_id=user.id)
        db.add(bpp)
    bpp.phase_choice = phase_choice
    db.commit()
    return RedirectResponse(url="/apostas", status_code=303)


@router.post("/brasil-jogo/{match_id}")
def save_brazil_match(
    match_id: int,
    neymar_in: str = Form(...),
    endrick_in: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if match is None or not match.is_brazil:
        raise HTTPException(status_code=404, detail="Jogo do Brasil não encontrado.")
    if not match_is_open(match):
        raise HTTPException(status_code=400, detail="Palpites deste jogo estão fechados.")

    bp = db.scalar(
        select(BrazilMatchPrediction).where(
            BrazilMatchPrediction.user_id == user.id,
            BrazilMatchPrediction.match_id == match_id,
        )
    )
    if bp is None:
        bp = BrazilMatchPrediction(user_id=user.id, match_id=match_id)
        db.add(bp)
    bp.neymar_in = neymar_in == "sim"
    bp.endrick_in = endrick_in == "sim"
    db.commit()
    return RedirectResponse(url="/#jogo-" + str(match_id), status_code=303)
