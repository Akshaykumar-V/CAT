"""Tests for the configurable CAT full mock workflow."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import MockConfiguration, MockSession, MockSessionQuestion
from app.mock_service import DEFAULT_MOCK_ID, utc_now


@pytest.fixture()
def mock_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)


def start(client: TestClient) -> dict:
    response = client.post("/mocks/start", json={"mock_id": DEFAULT_MOCK_ID})
    assert response.status_code == 200
    return response.json()


def test_mock_creation_and_start_hide_answer_keys(mock_client) -> None:
    client, db = mock_client

    configs = client.get("/mocks")
    assert configs.status_code == 200
    assert configs.json()[0]["total_questions"] == 9
    session = start(client)

    assert session["status"] == "IN_PROGRESS"
    assert session["current_section"] == "VARC"
    assert len(session["questions"]) == 3
    assert all("correct_answer" not in question for question in session["questions"])
    assert db.query(MockSessionQuestion).count() == 9
    assert len({row.question_id for row in db.query(MockSessionQuestion).all()}) == 9


def test_mock_answer_duplicate_and_review_marking(mock_client) -> None:
    client, _ = mock_client
    session = start(client)
    question_id = session["questions"][0]["question_id"]

    answer = client.post(
        f"/mocks/{session['id']}/answer",
        json={"question_id": question_id, "selected_answer": "A", "time_spent_seconds": 12, "marked_for_review": True},
    )
    duplicate = client.post(
        f"/mocks/{session['id']}/answer",
        json={"question_id": question_id, "selected_answer": "B", "time_spent_seconds": 2},
    )

    assert answer.status_code == 200
    assert answer.json()["questions"][0]["answered"] is True
    assert answer.json()["questions"][0]["marked_for_review"] is True
    assert duplicate.status_code == 409


def test_section_order_and_invalid_cross_section_answer(mock_client) -> None:
    client, _ = mock_client
    session = start(client)
    current_question = session["questions"][0]["question_id"]
    next_section_question = client.get(f"/mocks/{session['id']}").json()["questions"][-1]["question_id"]

    submitted = client.post(f"/mocks/{session['id']}/submit-section")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "SECTION_COMPLETE"

    next_session = client.get(f"/mocks/{session['id']}")
    assert next_session.status_code == 200
    assert next_session.json()["current_section"] == "DILR"
    cross_section = client.post(
        f"/mocks/{session['id']}/answer",
        json={"question_id": current_question, "selected_answer": "A"},
    )
    assert cross_section.status_code == 404
    assert next_section_question not in {question["question_id"] for question in next_session.json()["questions"]}


def test_section_timer_expires_server_side_and_reconnects(mock_client) -> None:
    client, db = mock_client
    session = start(client)
    stored_config = db.get(MockConfiguration, DEFAULT_MOCK_ID)
    stored_session = db.get(MockSession, session["id"])
    assert stored_config is not None and stored_session is not None
    stored_config.section_time_limit = {**stored_config.section_time_limit, "VARC": 1}
    stored_session.section_started_at = utc_now() - timedelta(seconds=5)
    db.commit()

    refreshed = client.get(f"/mocks/{session['id']}")

    assert refreshed.status_code == 200
    assert refreshed.json()["current_section"] == "DILR"
    assert refreshed.json()["status"] == "IN_PROGRESS"
    assert refreshed.json()["total_elapsed_seconds"] >= 0


def test_mock_result_review_and_active_protection(mock_client) -> None:
    client, _ = mock_client
    session = start(client)
    question_id = session["questions"][0]["question_id"]

    active_result = client.get(f"/mocks/{session['id']}/result")
    active_review = client.get(f"/mocks/{session['id']}/review")
    assert active_result.status_code == 400
    assert active_review.status_code == 403

    answered = client.post(
        f"/mocks/{session['id']}/answer",
        json={"question_id": question_id, "selected_answer": "A", "time_spent_seconds": 15},
    )
    assert answered.status_code == 200
    result = client.post(f"/mocks/{session['id']}/finish")
    review = client.get(f"/mocks/{session['id']}/review")

    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "COMPLETED"
    assert body["attempted"] == 1
    assert body["unanswered"] == 8
    assert len(body["sections"]) == 3
    assert review.status_code == 200
    assert review.json()["questions"][0]["correct_answer"] in {"A", "B", "C", "D"}
    assert review.json()["questions"][0]["explanation"]["steps"]


def test_invalid_mock_state_is_controlled(mock_client) -> None:
    client, _ = mock_client
    missing = client.get("/mocks/999999")
    invalid_config = client.post("/mocks/start", json={"mock_id": "missing-mock"})

    assert missing.status_code == 404
    assert invalid_config.status_code == 404
