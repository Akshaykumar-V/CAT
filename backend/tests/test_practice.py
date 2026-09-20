"""Tests for backend-only timed practice sessions."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import PracticeSession, Question
from app.practice_service import utc_now


client = TestClient(app)

START_REQUEST = {
    "section": "QA",
    "difficulty": "Medium",
    "question_count": 3,
    "time_limit_seconds": 1200,
}


def start_session() -> dict:
    response = client.post("/practice/start", json=START_REQUEST)
    assert response.status_code == 200
    return response.json()


def test_start_session_returns_requested_question_count() -> None:
    session = start_session()

    assert session["status"] == "active"
    assert len(session["questions"]) == 3
    assert [question["question_order"] for question in session["questions"]] == [1, 2, 3]


def test_active_session_does_not_expose_correct_answers() -> None:
    session = start_session()

    for question in session["questions"]:
        assert question["correct_answer"] is None
        assert question["explanation"] is None
        assert question["is_correct"] is None


def test_get_active_session_reports_answer_state() -> None:
    session = start_session()
    response = client.get(f"/practice/{session['id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert all(not question["answered"] for question in response.json()["questions"])


def test_submit_answer_and_prevent_duplicate_answers() -> None:
    session = start_session()
    question_id = session["questions"][0]["question_id"]
    answer = client.post(
        f"/practice/{session['id']}/answer",
        json={"question_id": question_id, "selected_answer": "A", "time_spent_seconds": 20},
    )
    duplicate = client.post(
        f"/practice/{session['id']}/answer",
        json={"question_id": question_id, "selected_answer": "B", "time_spent_seconds": 10},
    )

    assert answer.status_code == 200
    assert duplicate.status_code == 409


def test_finish_session_calculates_accuracy_and_unanswered_questions() -> None:
    session = start_session()
    first_question = session["questions"][0]
    db = SessionLocal()
    try:
        stored_question = db.get(Question, first_question["question_id"])
        assert stored_question is not None
        correct_label = next(
            label
            for label, value in first_question["options"].items()
            if value == stored_question.correct_answer
        )
    finally:
        db.close()

    answer = client.post(
        f"/practice/{session['id']}/answer",
        json={
            "question_id": first_question["question_id"],
            "selected_answer": correct_label,
            "time_spent_seconds": 15,
        },
    )
    summary = client.post(f"/practice/{session['id']}/finish")

    assert answer.status_code == 200
    assert summary.status_code == 200
    body = summary.json()
    assert body["status"] == "completed"
    assert body["attempted"] == 1
    assert body["unanswered"] == 2
    assert body["correct"] == 1
    assert body["incorrect"] == 0
    assert body["accuracy"] == 100.0


def test_expired_session_rejects_answers() -> None:
    session = start_session()
    session_id = session["id"]
    question_id = session["questions"][0]["question_id"]
    db = SessionLocal()
    try:
        stored_session = db.get(PracticeSession, session_id)
        assert stored_session is not None
        stored_session.started_at = utc_now() - timedelta(seconds=1300)
        db.commit()
    finally:
        db.close()

    response = client.post(
        f"/practice/{session_id}/answer",
        json={"question_id": question_id, "selected_answer": "A", "time_spent_seconds": 5},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Practice session has expired"
