"""Business logic for creating, timing, and scoring practice sessions."""

from datetime import datetime, timezone
import random

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import PracticeSession, Question, SessionQuestion
from .question_generator import TEMPLATES, generate_question
from .schemas import (
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeQuestion,
    PracticeSessionResponse,
    PracticeStartRequest,
    PracticeSummary,
    QuestionGenerationRequest,
)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Treat SQLite's timezone-naive timestamps as UTC when reading them back."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def elapsed_seconds(session: PracticeSession, now: datetime | None = None) -> int:
    """Calculate elapsed wall-clock time on the server, capped at the time limit."""
    current_time = now or utc_now()
    elapsed = int((current_time - as_utc(session.started_at)).total_seconds())
    return max(0, min(elapsed, session.time_limit_seconds))


def refresh_session_status(db: Session, session: PracticeSession) -> PracticeSession:
    """Mark an active session expired once its server-side deadline has passed."""
    if session.status == "active" and elapsed_seconds(session) >= session.time_limit_seconds:
        session.status = "expired"
        session.finished_at = utc_now()
        db.commit()
        db.refresh(session)
    return session


def _question_options(question: Question) -> dict[str, str]:
    return {
        "A": question.option_a or "",
        "B": question.option_b or "",
        "C": question.option_c or "",
        "D": question.option_d or "",
    }


def _answer_label(question: Question) -> str:
    """Find the option label whose text equals the stored correct-answer text."""
    for label, option in _question_options(question).items():
        if option == question.correct_answer:
            return label
    raise ValueError(f"Question {question.id} has no option matching its correct answer.")


def _session_questions(db: Session, session_id: int) -> list[tuple[SessionQuestion, Question]]:
    return (
        db.query(SessionQuestion, Question)
        .join(Question, SessionQuestion.question_id == Question.id)
        .filter(SessionQuestion.session_id == session_id)
        .order_by(SessionQuestion.question_order)
        .all()
    )


def _to_practice_question(
    session_question: SessionQuestion, question: Question, show_answers: bool
) -> PracticeQuestion:
    return PracticeQuestion(
        question_id=question.id,
        question_order=session_question.question_order,
        question_text=question.question_text,
        options=_question_options(question),
        answered=session_question.selected_answer is not None,
        selected_answer=session_question.selected_answer,
        is_correct=session_question.is_correct if show_answers else None,
        correct_answer=_answer_label(question) if show_answers else None,
        explanation=question.explanation if show_answers else None,
    )


def create_session(db: Session, request: PracticeStartRequest) -> PracticeSessionResponse:
    """Create a session and persist newly generated questions in its order."""
    templates = [key for key in TEMPLATES if key[0] == request.section]
    if not templates:
        raise HTTPException(status_code=400, detail="No templates exist for this section")

    session = PracticeSession(
        section=request.section,
        difficulty=request.difficulty,
        total_questions=request.question_count,
        started_at=utc_now(),
        time_limit_seconds=request.time_limit_seconds,
        status="active",
    )
    db.add(session)
    db.flush()

    for order in range(1, request.question_count + 1):
        section, topic, subtopic = random.choice(templates)
        generated = generate_question(
            QuestionGenerationRequest(
                section=section,
                topic=topic,
                subtopic=subtopic,
                difficulty=request.difficulty,
                question_type="MCQ",
            )
        )
        question = Question(
            section=generated.section,
            topic=generated.topic,
            subtopic=generated.subtopic,
            difficulty=generated.difficulty,
            question_type=generated.question_type,
            question_text=generated.question_text,
            option_a=generated.options[0],
            option_b=generated.options[1],
            option_c=generated.options[2],
            option_d=generated.options[3],
            correct_answer=generated.correct_answer,
            explanation=generated.explanation,
            source="Template-generated original question",
        )
        db.add(question)
        db.flush()
        db.add(
            SessionQuestion(
                session_id=session.id,
                question_id=question.id,
                question_order=order,
            )
        )

    db.commit()
    db.refresh(session)
    return get_session(db, session.id)


def get_session(db: Session, session_id: int) -> PracticeSessionResponse:
    """Return a session and hide answer keys when it remains active."""
    session = db.get(PracticeSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Practice session not found")
    session = refresh_session_status(db, session)
    show_answers = session.status != "active"
    questions = [
        _to_practice_question(session_question, question, show_answers)
        for session_question, question in _session_questions(db, session.id)
    ]
    return PracticeSessionResponse(
        id=session.id,
        section=session.section,
        difficulty=session.difficulty,
        total_questions=session.total_questions,
        started_at=as_utc(session.started_at),
        finished_at=as_utc(session.finished_at) if session.finished_at else None,
        time_limit_seconds=session.time_limit_seconds,
        status=session.status,
        elapsed_seconds=elapsed_seconds(session),
        questions=questions,
    )


def submit_answer(
    db: Session, session_id: int, request: PracticeAnswerRequest
) -> PracticeAnswerResponse:
    """Save one answer exactly once, using option labels A through D."""
    session = db.get(PracticeSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Practice session not found")
    session = refresh_session_status(db, session)
    if session.status == "expired":
        raise HTTPException(status_code=400, detail="Practice session has expired")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Practice session is not active")

    result = (
        db.query(SessionQuestion, Question)
        .join(Question, SessionQuestion.question_id == Question.id)
        .filter(
            SessionQuestion.session_id == session_id,
            SessionQuestion.question_id == request.question_id,
        )
        .first()
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Question is not part of this session")
    session_question, question = result
    if session_question.selected_answer is not None:
        raise HTTPException(status_code=409, detail="Question has already been answered")

    session_question.selected_answer = request.selected_answer
    session_question.is_correct = request.selected_answer == _answer_label(question)
    session_question.time_spent_seconds = request.time_spent_seconds
    session_question.answered_at = utc_now()
    db.commit()
    db.refresh(session_question)
    return PracticeAnswerResponse(
        question_id=question.id,
        selected_answer=session_question.selected_answer,
        is_correct=bool(session_question.is_correct),
        answered_at=as_utc(session_question.answered_at),
    )


def session_summary(db: Session, session: PracticeSession) -> PracticeSummary:
    """Calculate a server-timed score summary for a session."""
    session_questions = _session_questions(db, session.id)
    attempted = sum(item.selected_answer is not None for item, _ in session_questions)
    correct = sum(item.is_correct is True for item, _ in session_questions)
    incorrect = attempted - correct
    unanswered = session.total_questions - attempted
    total_time = elapsed_seconds(session)
    return PracticeSummary(
        session_id=session.id,
        status=session.status,
        total_questions=session.total_questions,
        attempted=attempted,
        correct=correct,
        incorrect=incorrect,
        unanswered=unanswered,
        accuracy=round((correct / attempted) * 100, 2) if attempted else 0.0,
        total_time_seconds=total_time,
        average_time_per_attempted_question_seconds=round(total_time / attempted, 2)
        if attempted
        else 0.0,
    )


def finish_session(db: Session, session_id: int) -> PracticeSummary:
    """Finish an active session, or return an already-expired session summary."""
    session = db.get(PracticeSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Practice session not found")
    session = refresh_session_status(db, session)
    if session.status == "active":
        session.status = "completed"
        session.finished_at = utc_now()
        db.commit()
        db.refresh(session)
    return session_summary(db, session)
