"""Área de administração: importar jogos, definir confrontos, lançar resultados e gabaritos."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_db
from app.models import Match, Settlement, User
from app.phases import PHASES_PROGRESS
from app.services import recompute_match, recompute_specials, seed_matches, seed_missing_matches
from app.templating import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("")
def dashboard(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    matches = list(db.scalars(select(Match).order_by(Match.kickoff_at)))
    settle = db.get(Settlement, 1)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "matches": matches,
            "settlement": settle,
            "phases_progress": PHASES_PROGRESS,
        },
    )


@router.post("/seed")
def run_seed(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    seed_matches(db)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/seed-missing")
def run_seed_missing(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    seed_missing_matches(db)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/match/{match_id}/teams")
def set_teams(
    match_id: int,
    home_team: str = Form(...),
    away_team: str = Form(...),
    teams_decided: str = Form(default="off"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    match.home_team = home_team.strip()
    match.away_team = away_team.strip()
    match.teams_decided = teams_decided == "on"
    match.is_brazil = "brasil" in (home_team + away_team).casefold()
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/match/{match_id}/resultado")
def set_result(
    match_id: int,
    home_score: int = Form(...),
    away_score: int = Form(...),
    neymar_played: str = Form(default="off"),
    endrick_played: str = Form(default="off"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    match.home_score = home_score
    match.away_score = away_score
    match.finished = True
    if match.is_brazil:
        match.neymar_played = neymar_played == "on"
        match.endrick_played = endrick_played == "on"
    db.commit()
    recompute_match(db, match)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/gabarito")
def set_gabarito(
    top_scorer: str = Form(default=""),
    brazil_final_phase: str = Form(default=""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    settle = db.get(Settlement, 1)
    if settle is None:
        settle = Settlement(id=1)
        db.add(settle)
    settle.top_scorer = top_scorer.strip()
    settle.brazil_final_phase = brazil_final_phase.strip()
    db.commit()
    recompute_specials(db)
    return RedirectResponse(url="/admin", status_code=303)
