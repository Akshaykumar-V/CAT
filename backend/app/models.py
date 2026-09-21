"""Database models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Question(Base):
    """A CAT-style practice question stored in the local database."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    section: Mapped[str] = mapped_column(String(20), index=True)
    topic: Mapped[str] = mapped_column(String(100), index=True)
    subtopic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20))
    question_type: Mapped[str] = mapped_column(String(100))
    question_text: Mapped[str] = mapped_column(Text)
    option_a: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_b: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_c: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_d: Mapped[str | None] = mapped_column(Text, nullable=True)
    correct_answer: Mapped[str] = mapped_column(String(10))
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100))


class PracticeSession(Base):
    """A timed practice session for one CAT section and difficulty."""

    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    section: Mapped[str] = mapped_column(String(20), index=True)
    difficulty: Mapped[str] = mapped_column(String(20))
    total_questions: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_limit_seconds: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)


class SessionQuestion(Base):
    """Links a saved question to a practice session and stores its answer state."""

    __tablename__ = "session_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("practice_sessions.id"), index=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    question_order: Mapped[int] = mapped_column(Integer)
    selected_answer: Mapped[str | None] = mapped_column(String(1), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MockConfiguration(Base):
    """Configurable mock definition backed by the existing question catalog."""

    __tablename__ = "mock_configurations"

    mock_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    total_questions: Mapped[int] = mapped_column(Integer)
    sections: Mapped[dict[str, int]] = mapped_column(JSON)
    section_order: Mapped[list[str]] = mapped_column(JSON)
    section_time_limit: Mapped[dict[str, int]] = mapped_column(JSON)
    total_time_limit: Mapped[int] = mapped_column(Integer)
    question_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="NOT_STARTED")


class MockSession(Base):
    """Server-authoritative state for one full mock attempt."""

    __tablename__ = "mock_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mock_id: Mapped[str] = mapped_column(ForeignKey("mock_configurations.mock_id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="IN_PROGRESS", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_section_index: Mapped[int] = mapped_column(Integer, default=0)
    section_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    section_time_used: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)


class MockSessionQuestion(Base):
    """Question answer state for a mock, without exposing its answer key."""

    __tablename__ = "mock_session_questions"
    __table_args__ = (
        UniqueConstraint("mock_session_id", "question_id", name="uq_mock_question"),
        UniqueConstraint("mock_session_id", "question_order", name="uq_mock_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mock_session_id: Mapped[int] = mapped_column(ForeignKey("mock_sessions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    section: Mapped[str] = mapped_column(String(20), index=True)
    question_order: Mapped[int] = mapped_column(Integer)
    selected_answer: Mapped[str | None] = mapped_column(String(1), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
