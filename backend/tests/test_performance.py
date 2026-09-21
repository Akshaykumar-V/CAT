"""Tests for completed-session performance calculations and API responses."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import PracticeSession, Question, SessionQuestion
from app.performance_service import (
    difficulty_performance,
    overall_performance,
    section_performance,
    topic_performance,
    weak_topics,
)


@pytest.fixture()
def performance_db():
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
def performance_client(performance_db):
    def override_get_db():
        yield performance_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def add_question(db, section: str, topic: str, difficulty: str) -> Question:
    question = Question(
        section=section,
        topic=topic,
        subtopic=topic,
        difficulty=difficulty,
        question_type="MCQ",
        question_text=f"Synthetic {topic} question",
        option_a="Correct",
        option_b="Wrong B",
        option_c="Wrong C",
        option_d="Wrong D",
        correct_answer="Correct",
        explanation="Synthetic explanation",
        source="Test data",
    )
    db.add(question)
    db.flush()
    return question


def seed_completed_sessions(db) -> None:
    now = datetime.now(timezone.utc)
    qa_session = PracticeSession(
        section="QA",
        difficulty="Medium",
        total_questions=3,
        started_at=now,
        finished_at=now,
        time_limit_seconds=1200,
        status="completed",
    )
    varc_session = PracticeSession(
        section="VARC",
        difficulty="Medium",
        total_questions=1,
        started_at=now,
        finished_at=now,
        time_limit_seconds=1200,
        status="completed",
    )
    db.add_all([qa_session, varc_session])
    db.flush()

    percentages = add_question(db, "QA", "Percentages", "Easy")
    time_work = add_question(db, "QA", "Time & Work", "Medium")
    algebra = add_question(db, "QA", "Algebra", "Hard")
    reading = add_question(db, "VARC", "Reading Comprehension", "Medium")
    db.add_all(
        [
            SessionQuestion(session_id=qa_session.id, question_id=percentages.id, question_order=1, selected_answer="A", is_correct=True, time_spent_seconds=80, answered_at=now),
            SessionQuestion(session_id=qa_session.id, question_id=time_work.id, question_order=2, selected_answer="B", is_correct=False, time_spent_seconds=120, answered_at=now),
            SessionQuestion(session_id=qa_session.id, question_id=algebra.id, question_order=3),
            SessionQuestion(session_id=varc_session.id, question_id=reading.id, question_order=1, selected_answer="A", is_correct=True, time_spent_seconds=40, answered_at=now),
        ]
    )
    db.commit()


def test_overall_accuracy_and_completed_session_count(performance_db) -> None:
    seed_completed_sessions(performance_db)
    overview = overall_performance(performance_db)

    assert overview["total_practice_sessions"] == 2
    assert overview["attempted"] == 3
    assert overview["correct"] == 2
    assert overview["incorrect"] == 1
    assert overview["unanswered"] == 1
    assert overview["accuracy"] == 66.67
    assert overview["questions_solved_by_section"] == {"VARC": 1, "DILR": 0, "QA": 2}


def test_section_topic_and_difficulty_metrics(performance_db) -> None:
    seed_completed_sessions(performance_db)
    sections = {item["section"]: item for item in section_performance(performance_db)}
    topics = {item["topic"]: item for item in topic_performance(performance_db)}
    difficulties = {item["difficulty"]: item for item in difficulty_performance(performance_db)}

    assert sections["QA"]["accuracy"] == 50.0
    assert sections["VARC"]["accuracy"] == 100.0
    assert topics["Time & Work"]["accuracy"] == 0.0
    assert difficulties["Easy"]["accuracy"] == 100.0
    assert difficulties["Hard"]["unanswered"] == 1


def test_weak_topic_categories_are_transparent(performance_db) -> None:
    seed_completed_sessions(performance_db)
    categories = weak_topics(performance_db)

    assert {item["topic"] for item in categories["strong_topics"]} == {
        "Percentages",
        "Reading Comprehension",
    }
    assert [item["topic"] for item in categories["needs_practice"]] == ["Algebra", "Time & Work"]


def test_empty_data_returns_zero_or_empty_results(performance_db) -> None:
    overview = overall_performance(performance_db)

    assert overview["total_practice_sessions"] == 0
    assert overview["attempted"] == 0
    assert overview["accuracy"] == 0.0
    assert topic_performance(performance_db) == []
    assert weak_topics(performance_db)["needs_practice"] == []


def test_dashboard_and_api_responses(performance_db, performance_client) -> None:
    seed_completed_sessions(performance_db)

    dashboard = performance_client.get("/performance/dashboard")
    overview = performance_client.get("/performance/overview")
    sections = performance_client.get("/performance/sections")
    topics = performance_client.get("/performance/topics")
    difficulty = performance_client.get("/performance/difficulty")
    categories = performance_client.get("/performance/weak-topics")

    assert dashboard.status_code == 200
    assert dashboard.json()["overall"]["accuracy"] == 66.67
    assert "needs_practice" in dashboard.json()
    assert overview.status_code == sections.status_code == topics.status_code == 200
    assert difficulty.status_code == categories.status_code == 200
