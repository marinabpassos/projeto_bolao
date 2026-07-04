"""Páginas de leitura: jogos, ranking e regras."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.bracket import jogos_view
from app.data_loader import load_players
from app.db import get_db
from app.models import (
    ArtilheiroPrediction,
    BrazilMatchPrediction,
    BrazilProgressPrediction,
    Match,
    Prediction,
    User,
)
from app.phases import MATCH_STAGES
from app.services import (
    brazil_progress_is_open,
    compute_ranking,
    current_artilheiro_tier,
    match_is_open,
    now_utc,
)
from app.templating import templates

router = APIRouter()


@router.get("/")
def home(request: Request, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = list(db.scalars(select(Match).order_by(Match.kickoff_at)))
    now = now_utc()

    my_preds: dict[int, Prediction] = {}
    my_br: dict[int, BrazilMatchPrediction] = {}
    if user:
        my_preds = {
            p.match_id: p
            for p in db.scalars(select(Prediction).where(Prediction.user_id == user.id))
        }
        my_br = {
            b.match_id: b
            for b in db.scalars(
                select(BrazilMatchPrediction).where(BrazilMatchPrediction.user_id == user.id)
            )
        }

    # Agrupa por fase preservando a ordem das fases.
    groups = []
    for stage in MATCH_STAGES:
        stage_matches = [m for m in matches if m.stage == stage]
        if stage_matches:
            groups.append((stage, stage_matches))

    view = jogos_view(matches, request.query_params.get("fase"))

    return templates.TemplateResponse(
        "jogos.html",
        {
            "request": request,
            "user": user,
            "groups": groups,
            "view": view,
            "past_groups": [(s, ms) for s, ms in groups if s in view["past_stages"]],
            "my_preds": my_preds,
            "my_br": my_br,
            "is_open": {m.id: match_is_open(m, now) for m in matches},
            "saved": request.query_params.get("saved"),
        },
    )


@router.get("/ranking")
def ranking(request: Request, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = compute_ranking(db)
    pos = 1
    for i, row in enumerate(rows):
        if i > 0 and rows[i]["total"] < rows[i - 1]["total"]:
            pos = i + 1
        row["pos"] = pos
    my_row, my_pos = None, None
    if user:
        for r in rows:
            if r["user"].id == user.id:
                my_row, my_pos = r, r["pos"]
                break
    return templates.TemplateResponse(
        "ranking.html",
        {"request": request, "user": user, "ranking": rows, "my_row": my_row, "my_pos": my_pos},
    )


@router.get("/regras")
def regras(request: Request, user: User | None = Depends(get_current_user)):
    return templates.TemplateResponse("regras.html", {"request": request, "user": user})


@router.get("/apostas")
def apostas(request: Request, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    artilheiro = brazil_progress = None
    if user:
        artilheiro = db.scalar(
            select(ArtilheiroPrediction).where(ArtilheiroPrediction.user_id == user.id)
        )
        brazil_progress = db.scalar(
            select(BrazilProgressPrediction).where(BrazilProgressPrediction.user_id == user.id)
        )
    return templates.TemplateResponse(
        "apostas.html",
        {
            "request": request,
            "user": user,
            "artilheiro": artilheiro,
            "brazil_progress": brazil_progress,
            "players": load_players(),
            "current_tier": current_artilheiro_tier(db),
            "progress_open": brazil_progress_is_open(db),
            "saved": request.query_params.get("saved"),
        },
    )
