"""Tests for history-aware adaptive practice selection."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adaptive_service import difficulty_options_for_accuracy
from app.database import Base, get_db
from app.main import app
from app.models import PracticeSession, Question, SessionQuestion


@pytest.fixture()
def adaptive_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)()
    try:
        yield test_session
    finally:
        test_session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def adaptive_client(adaptive_db):
    def override_get_db():
        yield adaptive_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def add_question(
    db,
    topic: str,
    subtopic: str,
    difficulty: str,
    question_number: int,
) -> Question:
    question = Question(
        section="QA",
        topic=topic,
        subtopic=subtopic,
        difficulty=difficulty,
        question_type="MCQ",
        question_text=f"Question {question_number} for {subtopic}",
        option_a="Correct",
        option_b="Wrong B",
        option_c="Wrong C",
        option_d="Wrong D",
        correct_answer="Correct",
        explanation="Test explanation",
        source="Test data",
    )
    db.add(question)
    db.flush()
    return question


def add_completed_session(db, questions: list[tuple[Question, bool]], finished_at: datetime):
    session = PracticeSession(
        section="QA",
        difficulty="Medium",
        total_questions=len(questions),
        started_at=finished_at - timedelta(minutes=10),
        finished_at=finished_at,
        time_limit_seconds=1200,
        status="completed",
    )
    db.add(session)
    db.flush()
    for order, (question, is_correct) in enumerate(questions, start=1):
        db.add(
            SessionQuestion(
                session_id=session.id,
                question_id=question.id,
                question_order=order,
                selected_answer="A",
                is_correct=is_correct,
                time_spent_seconds=30,
                answered_at=finished_at,
            )
        )
    db.commit()
    return session


def seed_history(adaptive_db):
    now = datetime.now(timezone.utc)
    weak_old = add_question(adaptive_db, "Arithmetic", "Time & Work", "Easy", 1)
    weak_new = add_question(adaptive_db, "Arithmetic", "Time & Work", "Easy", 2)
    weak_medium = add_question(adaptive_db, "Arithmetic", "Time & Work", "Medium", 3)
    strong = add_question(adaptive_db, "Arithmetic", "Percentages", "Medium", 4)
    add_completed_session(adaptive_db, [(weak_old, True)], now - timedelta(days=2))
    add_completed_session(
        adaptive_db,
        [(weak_new, False), (strong, True)],
        now,
    )
    return weak_old, weak_new, weak_medium, strong


def session_question_rows(db, session_id: int):
    return (
        db.query(SessionQuestion, Question)
        .join(Question, SessionQuestion.question_id == Question.id)
        .filter(SessionQuestion.session_id == session_id)
        .order_by(SessionQuestion.question_order)
        .all()
    )


def test_difficulty_selection_rules_are_configurable() -> None:
    assert difficulty_options_for_accuracy(40) == ("Easy", "Easy", "Medium")
    assert difficulty_options_for_accuracy(60) == ("Easy", "Medium")
    assert difficulty_options_for_accuracy(75) == ("Medium", "Medium", "Hard")
    assert difficulty_options_for_accuracy(90) == ("Medium", "Hard")


def test_weak_topic_is_prioritized_and_recent_history_is_weighted(adaptive_db) -> None:
    seed_history(adaptive_db)
    response = adaptive_client_for(adaptive_db).post(
        "/practice/adaptive-start",
        json={"section": "QA", "question_count": 1, "time_limit_seconds": 1200},
    )

    assert response.status_code == 200
    session = adaptive_db.get(PracticeSession, response.json()["id"])
    assert session is not None
    row = session_question_rows(adaptive_db, session.id)[0][1]
    assert row.subtopic == "Time & Work"


def adaptive_client_for(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_strong_topic_gets_maintenance_questions(adaptive_db) -> None:
    seed_history(adaptive_db)
    client = adaptive_client_for(adaptive_db)
    response = client.post(
        "/practice/adaptive-start",
        json={"section": "QA", "question_count": 5, "time_limit_seconds": 1200},
    )

    assert response.status_code == 200
    rows = session_question_rows(adaptive_db, response.json()["id"])
    assert any(question.subtopic == "Percentages" for _, question in rows)


def test_unseen_questions_are_preferred_and_fallback_fills_count(adaptive_db) -> None:
    weak_old, weak_new, weak_medium, _ = seed_history(adaptive_db)
    response = adaptive_client_for(adaptive_db).post(
        "/practice/adaptive-start",
        json={"section": "QA", "question_count": 4, "time_limit_seconds": 1200},
    )

    assert response.status_code == 200
    rows = session_question_rows(adaptive_db, response.json()["id"])
    ids = {question.id for _, question in rows}
    assert len(rows) == 4
    assert weak_old.id not in ids
    assert weak_new.id not in ids
    assert weak_medium.id in ids


def test_adaptive_session_supports_all_sections(adaptive_client) -> None:
    for section in ("VARC", "DILR", "QA"):
        response = adaptive_client.post(
            "/practice/adaptive-start",
            json={"section": section, "question_count": 2, "time_limit_seconds": 1200},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"
        assert response.json()["difficulty"] == "Adaptive"


def test_recommendation_endpoint_reports_weak_topics(adaptive_db) -> None:
    seed_history(adaptive_db)
    response = adaptive_client_for(adaptive_db).get("/practice/recommendation?section=QA")

    assert response.status_code == 200
    body = response.json()
    assert body["section"] == "QA"
    assert body["recommended_topics"][0]["topic"] == "Time & Work"
    assert body["recommended_topics"][0]["reason"] == "Low recent accuracy"
    assert body["recommended_difficulties"] == ["Easy", "Medium"]


def test_no_history_returns_transparent_default_recommendation(adaptive_client) -> None:
    response = adaptive_client.get("/practice/recommendation")

    assert response.status_code == 200
    body = response.json()
    assert body["section"] == "QA"
    assert body["recommended_topics"]
    assert body["recommended_topics"][0]["reason"] == "No previous practice history"
    assert body["recommended_difficulties"] == ["Easy", "Medium"]