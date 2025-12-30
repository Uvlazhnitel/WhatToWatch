from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Europe/Riga")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    watched_films: Mapped[List["WatchedFilm"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    recommendations: Mapped[List["AgentRecommendation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    taste_profile: Mapped[Optional["TasteProfile"]] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)


class WatchedFilm(Base):
    __tablename__ = "watched_films"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 0..5, допускаем шаг 0.5 (Numeric(2,1) подходит: 0.0..9.9, но мы ограничим CHECK)
    your_rating: Mapped[Optional[float]] = mapped_column(Numeric(2, 1), nullable=True)
    your_review: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    watched_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # letterboxd / agent / manual
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="letterboxd")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="watched_films")

    __table_args__ = (
        CheckConstraint("your_rating IS NULL OR (your_rating >= 0 AND your_rating <= 5)", name="chk_watched_rating_range"),
        CheckConstraint("source IN ('letterboxd','agent','manual')", name="chk_watched_source"),
        Index("ix_watched_user_tmdb", "user_id", "tmdb_id"),
    )


class AgentRecommendation(Base):
    __tablename__ = "agent_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    context_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    user: Mapped["User"] = relationship(back_populates="recommendations")
    items: Mapped[List["AgentRecommendationItem"]] = relationship(back_populates="recommendation", cascade="all, delete-orphan")


class AgentRecommendationItem(Base):
    __tablename__ = "agent_recommendation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("agent_recommendations.id", ondelete="CASCADE"), nullable=False, index=True)

    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # safe / adjacent / wildcard
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, server_default="safe")
    # suggested / watched / skipped
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="suggested")

    explanation_shown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recommendation: Mapped["AgentRecommendation"] = relationship(back_populates="items")
    feedback: Mapped[Optional["Feedback"]] = relationship(back_populates="recommendation_item", cascade="all, delete-orphan", uselist=False)

    __table_args__ = (
        CheckConstraint("strategy IN ('safe','adjacent','wildcard')", name="chk_item_strategy"),
        CheckConstraint("status IN ('suggested','watched','skipped')", name="chk_item_status"),
        Index("ix_rec_items_recid_pos", "recommendation_id", "position"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_item_id: Mapped[int] = mapped_column(
        ForeignKey("agent_recommendation_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    your_rating: Mapped[Optional[float]] = mapped_column(Numeric(2, 1), nullable=True)
    your_review: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    recommendation_item: Mapped["AgentRecommendationItem"] = relationship(back_populates="feedback")

    __table_args__ = (
        CheckConstraint("your_rating IS NULL OR (your_rating >= 0 AND your_rating <= 5)", name="chk_feedback_rating_range"),
    )


class TasteProfile(Base):
    __tablename__ = "taste_profile"

    # один профиль на пользователя
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    summary_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    # предпочтения и избегания в jsonb
    weights_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    avoids_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="taste_profile")

class TmdbMovieDetailsCache(Base):
    __tablename__ = "tmdb_movie_details_cache"

    tmdb_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_tmdb_details_expires", "expires_at"),
    )


class TmdbMovieKeywordsCache(Base):
    __tablename__ = "tmdb_movie_keywords_cache"

    tmdb_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_tmdb_keywords_expires", "expires_at"),
    )
