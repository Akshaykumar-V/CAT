"""End-to-end smoke coverage for the core student workflow."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def workflow_client():
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


def test_complete_adaptive_student_workflow(workflow_client) -> None:
    client, db = workflow_client

    initial_dashboard = client.get("/performance/dashboard")
    assert initial_dashboard.status_code == 200
    assert initial_dashboard.json()["overall"]["attempted"] == 0

    session_response = client.post(
        "/practice/adaptive-start",
        json={"section": "QA", "question_count": 2, "time_limit_seconds": 1200},
    )
    assert session_response.status_code == 200
    session = session_response.json()
    assert session["status"] == "active"
    assert len(session["questions"]) == 2
    assert len({item["question_id"] for item in session["questions"]}) == 2
    assert all(item["correct_answer"] is None for item in session["questions"])

    first_question = session["questions"][0]
    blocked = client.get(f"/questions/{first_question['question_id']}/explanation")
    assert blocked.status_code == 403

    answer = client.post(
        f"/practice/{session['id']}/answer",
        json={"question_id": first_question["question_id"], "selected_answer": "A", "time_spent_seconds": 18},
    )
    assert answer.status_code == 200
    assert answer.json()["question_id"] == first_question["question_id"]

    explanation = client.post(
        f"/questions/{first_question['question_id']}/explanation",
        json={"selected_answer": "A"},
    )
    assert explanation.status_code == 200
    assert explanation.json()["question_id"] == first_question["question_id"]
    assert explanation.json()["steps"]

    active_state = client.get(f"/practice/{session['id']}").json()
    assert active_state["questions"][0]["selected_answer"] == "A"
    assert active_state["questions"][0]["correct_answer"] is None
    assert active_state["questions"][1]["answered"] is False

    finished = client.post(f"/practice/{session['id']}/finish")
    assert finished.status_code == 200
    assert finished.json()["attempted"] == 1
    assert finished.json()["unanswered"] == 1

    updated_dashboard = client.get("/performance/dashboard").json()
    assert updated_dashboard["overall"]["attempted"] == 1
    assert updated_dashboard["overall"]["total_practice_sessions"] == 1

    second_session = client.post(
        "/practice/adaptive-start",
        json={"section": "QA", "question_count": 1, "time_limit_seconds": 1200},
    )
    assert second_session.status_code == 200
    assert second_session.json()["status"] == "active"
