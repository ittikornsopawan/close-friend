from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _json_column():
    """JSONB on Postgres, portable JSON (TEXT-serialized) on SQLite for tests."""
    return JSON().with_variant(JSONB(), "postgresql")


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tagline: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    avatar_initials: Mapped[str] = mapped_column(String(4), nullable=False)
    tags: Mapped[list] = mapped_column(_json_column(), nullable=False, default=list)
    character: Mapped[dict] = mapped_column(_json_column(), nullable=False)
    boundaries: Mapped[list] = mapped_column(_json_column(), nullable=False, default=list)
    emotion_rules: Mapped[list] = mapped_column(_json_column(), nullable=False, default=list)
    relationship_stages: Mapped[list] = mapped_column(_json_column(), nullable=False, default=list)
    baseline_state: Mapped[dict] = mapped_column(_json_column(), nullable=False)
    research_scope: Mapped[dict] = mapped_column(_json_column(), nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PersonaState(Base):
    __tablename__ = "persona_states"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    persona_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("personas.id"), nullable=False, index=True
    )
    emotion: Mapped[str] = mapped_column(String(50), nullable=False)
    emotion_intensity: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    emotion_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationship_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    rapport_score: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    context_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    known_facts: Mapped[list] = mapped_column(_json_column(), nullable=False, default=list)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    persona: Mapped["Persona"] = relationship()


class EpisodicEvent(Base):
    __tablename__ = "episodic_events"
    __table_args__ = (
        Index("ix_episodic_events_conversation_turn", "conversation_id", "turn_index"),
    )

    # Integer (not BigInteger) — SQLite's implicit ROWID autoincrement alias
    # only kicks in for a literal INTEGER PRIMARY KEY column, needed so the
    # sqlite-backed test fixture behaves the same as Postgres SERIAL.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("persona_states.conversation_id"), nullable=False, index=True
    )
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    emotion_impact: Mapped[dict] = mapped_column(_json_column(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
