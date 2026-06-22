"""Salvar palpites de placar."""

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import Match, Prediction, User
from app.services import match_is_open

router = APIRouter(prefix="/palpite", tags=["palpites"])


@router.post("/{match_id}")
def save_prediction(
    match_id: int,
    home_pred: int = Form(...),
    away_pred: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    if not match_is_open(match):
        raise HTTPException(status_code=400, detail="Palpites deste jogo estão fechados.")
    if home_pred < 0 or away_pred < 0:
        raise HTTPException(status_code=400, detail="Placar não pode ser negativo.")

    pred = db.scalar(
        select(Prediction).where(
            Prediction.user_id == user.id, Prediction.match_id == match_id
        )
    )
    if pred is None:
        pred = Prediction(user_id=user.id, match_id=match_id)
        db.add(pred)
    pred.home_pred = home_pred
    pred.away_pred = away_pred
    db.commit()
    return RedirectResponse(url="/#jogo-" + str(match_id), status_code=303)
