"""Engine e sessão do SQLAlchemy.

Em ambiente serverless (Vercel) cada request é uma invocação curta, então usamos
`NullPool` (sem pool persistente) e apontamos para o connection pooler do Supabase
(porta 6543, modo transaction).
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _normalize_db_url(url: str) -> str:
    """Garante o driver psycopg para URLs Postgres (Neon, Supabase, etc.).

    Provedores entregam a string como `postgres://` ou `postgresql://`; o
    SQLAlchemy precisa de `postgresql+psycopg://` para usar o psycopg 3.
    """
    if not url:
        return "sqlite+pysqlite:///:memory:"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_settings = get_settings()
engine = create_engine(
    _normalize_db_url(_settings.database_url),
    poolclass=NullPool,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependência FastAPI: abre e fecha uma sessão por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
