"""Modelos ORM do bolão."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="")
    picture_url: Mapped[str] = mapped_column(String, default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    stage: Mapped[str] = mapped_column(String)  # grupos/16avos/oitavas/quartas/semi/final
    round: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-3 na fase de grupos
    home_team: Mapped[str] = mapped_column(String)
    away_team: Mapped[str] = mapped_column(String)
    teams_decided: Mapped[bool] = mapped_column(Boolean, default=True)
    is_brazil: Mapped[bool] = mapped_column(Boolean, default=False)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    neymar_played: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    endrick_played: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_pred_user_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    home_pred: Mapped[int] = mapped_column(Integer)
    away_pred: Mapped[int] = mapped_column(Integer)
    points: Mapped[int] = mapped_column(Integer, default=0)


class BrazilMatchPrediction(Base):
    __tablename__ = "brazil_match_predictions"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_brmatch_user_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    neymar_in: Mapped[bool] = mapped_column(Boolean)
    endrick_in: Mapped[bool] = mapped_column(Boolean)
    points: Mapped[int] = mapped_column(Integer, default=0)


class ArtilheiroPrediction(Base):
    __tablename__ = "artilheiro_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    player: Mapped[str] = mapped_column(String)
    tier_points_at_edit: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    points: Mapped[int] = mapped_column(Integer, default=0)


class BrazilProgressPrediction(Base):
    __tablename__ = "brazil_progress_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    phase_choice: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    points: Mapped[int] = mapped_column(Integer, default=0)


class Settlement(Base):
    """Gabaritos globais do torneio (uma única linha, id=1)."""

    __tablename__ = "settlement"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    top_scorer: Mapped[str] = mapped_column(String, default="")
    brazil_final_phase: Mapped[str] = mapped_column(String, default="")
