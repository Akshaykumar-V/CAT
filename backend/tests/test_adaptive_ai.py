"""Tests for adaptive practice using existing and generated questions."""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adaptive_service import create_adaptive_session
from app.database import Base
from app.models import PracticeSession, Question, SessionQuestion
from app.schemas import AdaptivePracticeStartRequest, AIQuestionResponse, QuestionGenerationRequest
from app.question_generator import generate_question


@pytest.fixture()
def adaptive_ai_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def add_question(db, number: int, difficulty: str = "Easy", source: str = "PYQ metadata"):
    question = Question(
        section="QA",
        topic="Arithmetic",
        subtopic="Percentages",
        difficulty=difficulty,
        question_type="MCQ",
        question_text=f"Existing question {number}",
        option_a="Correct",
        option_b="Wrong B",
        option_c="Wrong C",
        option_d="Wrong D",
        correct_answer="Correct",
        explanation="The arithmetic supports the answer.",
        source=source,
    )
    db.add(question)
    db.flush()
    return question


def start_request(count: int) -> AdaptivePracticeStartRequest:
    return AdaptivePracticeStartRequest(
        section="QA", question_count=count, time_limit_seconds=1200
    )


def generated_response(request: QuestionGenerationRequest, source: str = "template"):
    question = generate_question(request)
    return AIQuestionResponse(
        question=question,
        blueprint={
            "section": question.section,
            "topic": question.topic,
            "subtopic": question.subtopic,
            "question_type": question.question_type,
            "difficulty": question.difficulty,
            "concepts": ["test_concept"],
            "number_of_steps": 2,
            "reasoning_level": "medium",
            "calculation_load": "medium",
            "information_density": "medium",
            "trap_type": "test_trap",
            "expected_time_seconds": 120,
        },
        generator=source,
        validation={"valid": True},
    )


def session_rows(db, session_id):
    return (
        db.query(SessionQuestion, Question)
        .join(Question, SessionQuestion.question_id == Question.id)
        .filter(SessionQuestion.session_id == session_id)
        .order_by(SessionQuestion.question_order)
        .all()
    )


def test_enough_existing_questions_does_not_call_generator(adaptive_ai_db):
    existing = [
        add_question(adaptive_ai_db, number, "Medium" if number == 2 else "Easy")
        for number in range(3)
    ]
    calls = 0

    def generator(_request):
        nonlocal calls
        calls += 1
        raise AssertionError("generator should not be called")

    response = create_adaptive_session(adaptive_ai_db, start_request(3), ai_generator=generator)
    rows = session_rows(adaptive_ai_db, response.id)

    assert calls == 0
    assert {question.id for _, question in rows} == {question.id for question in existing}
    assert all(question.source == "PYQ metadata" for _, question in rows)


def test_mixed_existing_and_llm_generated_questions(adaptive_ai_db):
    existing = add_question(adaptive_ai_db, 1)
    calls = []

    def generator(request):
        calls.append(request)
        return generated_response(request, "llm")

    response = create_adaptive_session(adaptive_ai_db, start_request(3), ai_generator=generator)
    rows = session_rows(adaptive_ai_db, response.id)

    assert len(rows) == 3
    assert len(calls) == 2
    assert sum(question.id == existing.id for _, question in rows) == 1
    assert sum(question.source == "llm-generated original adaptive question" for _, question in rows) == 2
    assert all(question.correct_answer is not None for _, question in rows)
    assert response.questions[0].correct_answer is None
    assert response.questions[0].explanation is None
    assert response.questions[0].source


def test_llm_unavailable_uses_template_fallback(adaptive_ai_db, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    response = create_adaptive_session(adaptive_ai_db, start_request(1))
    rows = session_rows(adaptive_ai_db, response.id)

    assert rows[0][1].source == "template-generated original adaptive question"


def test_duplicate_generated_questions_are_retried(adaptive_ai_db):
    calls = 0
    base_response = generated_response(
        QuestionGenerationRequest(
            section="QA",
            topic="Algebra",
            subtopic="Algebra",
            difficulty="Easy",
            question_type="MCQ",
        ),
        "llm",
    )

    def generator(request):
        nonlocal calls
        calls += 1
        response = base_response.model_copy(deep=True)
        if calls <= 2:
            return response
        response.question = response.question.model_copy(
            update={"question_text": f"Unique generated question {calls}"}
        )
        return response

    response = create_adaptive_session(adaptive_ai_db, start_request(2), ai_generator=generator)
    rows = session_rows(adaptive_ai_db, response.id)

    assert calls == 3
    assert len({question.question_text for _, question in rows}) == 2


def test_generation_failure_rolls_back_and_returns_controlled_error(adaptive_ai_db):
    def failing_generator(_request):
        raise HTTPException(status_code=503, detail="provider unavailable")

    with pytest.raises(HTTPException) as error:
        create_adaptive_session(adaptive_ai_db, start_request(1), ai_generator=failing_generator)

    assert error.value.status_code == 503
    assert adaptive_ai_db.query(PracticeSession).count() == 0
    assert adaptive_ai_db.query(Question).count() == 0


def test_generated_question_matches_adaptive_request(adaptive_ai_db):
    captured = []

    def generator(request):
        captured.append(request)
        return generated_response(request, "llm")

    create_adaptive_session(adaptive_ai_db, start_request(1), ai_generator=generator)

    assert captured[0].section == "QA"
    assert (captured[0].section, captured[0].topic, captured[0].subtopic) in {
        ("QA", "Arithmetic", "Percentages"),
        ("QA", "Arithmetic", "Profit & Loss"),
        ("QA", "Arithmetic", "Ratio"),
        ("QA", "Arithmetic", "Averages"),
        ("QA", "Arithmetic", "Time & Work"),
        ("QA", "Arithmetic", "Time, Speed & Distance"),
        ("QA", "Algebra", "Algebra"),
        ("QA", "Number System", "Number System"),
    }
    assert captured[0].question_type == "MCQ"
    assert captured[0].difficulty in {"Easy", "Medium"}