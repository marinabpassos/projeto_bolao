"""Aplicação FastAPI do Bolão da Copa 2026."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.config import get_settings
from app.routers import admin, pages, predictions, special

settings = get_settings()

app = FastAPI(title="Bolão da Copa 2026")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth_router)
app.include_router(pages.router)
app.include_router(predictions.router)
app.include_router(special.router)
app.include_router(admin.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}
