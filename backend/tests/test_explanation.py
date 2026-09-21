"""Tests for protected, verified explanation mode."""

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.explanation_service import answer_label, independently_calculate
from app.llm_provider import LLMProviderError
from app.main import app
from app.models import Question
from app.schemas import ExplanationDraft, ExplanationResponse


client = TestClient(app)
START_REQUEST = {
    "section": "QA",
    "difficulty": "Medium",
    "question_count": 1,
    "time_limit_seconds": 1200,
}


def start_answered_session() -> tuple[dict, str]:
    session = client.post("/practice/start", json=START_REQUEST).json()
    question = session["questions"][0]
    selected = "A"
    response = client.post(
        f"/practice/{session['id']}/answer",
        json={"question_id": question["question_id"], "selected_answer": selected, "time_spent_seconds": 10},
    )
    assert response.status_code == 200
    return session, selected


def test_explanation_schema_contains_structured_educational_fields() -> None:
    fields = ExplanationResponse.model_fields

    assert {"question_id", "correct_answer", "short_answer", "concept", "approach", "steps", "shortcut", "common_mistake", "difficulty_note"}.issubset(fields)


def test_active_session_protects_explanation_until_answered() -> None:
    session = client.post("/practice/start", json=START_REQUEST).json()
    question_id = session["questions"][0]["question_id"]

    response = client.get(f"/questions/{question_id}/explanation")

    assert response.status_code == 403
    assert "before requesting" in response.json()["detail"]


def test_correct_answer_explanation_returns_verified_answer() -> None:
    session, _ = start_answered_session()
    question = session["questions"][0]
    response = client.post(
        f"/questions/{question['question_id']}/explanation",
        json={"selected_answer": "A"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["question_id"] == question["question_id"]
    assert body["correct_answer"] in {"A", "B", "C", "D"}
    assert body["result"] == ("correct" if body["correct_answer"] == "A" else "incorrect")
    assert body["steps"]


def test_incorrect_answer_explanation_is_specific_without_shaming() -> None:
    session, _ = start_answered_session()
    question_id = session["questions"][0]["question_id"]
    db = SessionLocal()
    try:
        stored_question = db.get(Question, question_id)
        assert stored_question is not None
        wrong_label = next(label for label in ("A", "B", "C", "D") if label != answer_label(stored_question))
    finally:
        db.close()
    response = client.post(
        f"/questions/{question_id}/explanation",
        json={"selected_answer": wrong_label},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "incorrect"
    assert f"You selected {wrong_label}" in body["common_mistake"]
    assert "normal" in body["common_mistake"]


def test_numerical_verification_calculates_template_answer() -> None:
    assert independently_calculate("A cyclist travels at 40 km/h for 3 hours at a constant speed.") == "120"
    assert independently_calculate("A subscription costs Rs. 200. Its price is increased by 15%.") == "230"


class ExplanationProvider:
    def __init__(self, draft):
        self.draft = draft

    def generate_explanation(self, question):
        if isinstance(self.draft, Exception):
            raise self.draft
        return self.draft


def test_llm_explanation_is_accepted_only_when_it_references_answer(monkeypatch) -> None:
    session, _ = start_answered_session()
    question = session["questions"][0]
    db = SessionLocal()
    try:
        stored_question = db.get(Question, question["question_id"])
        assert stored_question is not None
        correct_label = answer_label(stored_question)
    finally:
        db.close()
    draft = ExplanationDraft(
        short_answer=f"The answer is {stored_question.correct_answer} (option {correct_label}).",
        concept=question["subtopic"] or question["topic"],
        approach=f"Apply the relationship in this question: {stored_question.question_text}",
        steps=[f"Compare the values and select option {correct_label}.", "Check the result against the options."],
        shortcut="Estimate before calculating.",
        common_mistake="Skipping the final comparison.",
        difficulty_note="This is a focused medium-level question.",
    )

    from app import explanation_service

    monkeypatch.setattr(explanation_service, "configured_llm_provider", lambda: ExplanationProvider(draft))
    response = client.get(f"/questions/{question['question_id']}/explanation")

    assert response.status_code == 200
    assert response.json()["short_answer"] == draft.short_answer


def test_malformed_llm_response_falls_back_to_deterministic(monkeypatch) -> None:
    session, _ = start_answered_session()
    question_id = session["questions"][0]["question_id"]

    from app import explanation_service

    monkeypatch.setattr(explanation_service, "configured_llm_provider", lambda: ExplanationProvider(LLMProviderError("bad JSON")))
    response = client.get(f"/questions/{question_id}/explanation")

    assert response.status_code == 200
    assert response.json()["steps"]
    assert response.json()["short_answer"].startswith("The answer is")