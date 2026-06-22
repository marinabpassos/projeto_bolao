"""Autenticação via Google OAuth (Authlib) + sessão por cookie."""

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

settings = get_settings()

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    redirect_uri = f"{settings.base_url}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or {}
    email = info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Não foi possível obter o e-mail do Google.")

    user = db.scalar(select(User).where(User.email == email))
    is_admin = settings.is_admin(email)
    if user is None:
        user = User(
            email=email,
            name=info.get("name", ""),
            picture_url=info.get("picture", ""),
            is_admin=is_admin,
        )
        db.add(user)
    else:
        user.name = info.get("name", user.name)
        user.picture_url = info.get("picture", user.picture_url)
        user.is_admin = is_admin
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Usuário logado (ou None). Não bloqueia rotas públicas."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    """Dependência para rotas que exigem login (redireciona para o Google)."""
    if user is None:
        raise HTTPException(status_code=307, headers={"Location": "/auth/login"})
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    """Dependência para rotas de administração."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito à organização do bolão.")
    return user
