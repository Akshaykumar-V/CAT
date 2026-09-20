"""Tests for original template-based question generation."""

from fastapi.testclient import TestClient

from app.main import app
from app.question_generator import TEMPLATES, generate_question
from app.schemas import QuestionGenerationRequest


client = TestClient(app)

PERCENTAGES_REQUEST = {
    "section": "QA",
    "topic": "Arithmetic",
    "subtopic": "Percentages",
    "difficulty": "Medium",
    "question_type": "MCQ",
}


def test_generated_question_has_required_fields_and_valid_answer() -> None:
    question = generate_question(QuestionGenerationRequest(**PERCENTAGES_REQUEST))

    assert question.question_text
    assert len(question.options) == 4
    assert question.correct_answer in question.options
    assert question.explanation
    assert question.section == "QA"
    assert question.subtopic == "Percentages"


def test_numeric_questions_can_generate_different_values() -> None:
    request = QuestionGenerationRequest(**PERCENTAGES_REQUEST)
    questions = [generate_question(request).question_text for _ in range(8)]

    assert len(set(questions)) > 1


def test_every_supported_template_generates_a_valid_mcq() -> None:
    for section, topic, subtopic in TEMPLATES:
        question = generate_question(
            QuestionGenerationRequest(
                section=section,
                topic=topic,
                subtopic=subtopic,
                difficulty="Medium",
                question_type="MCQ",
            )
        )

        assert len(question.options) == 4
        assert question.correct_answer in question.options


def test_generate_question_api_returns_one_question() -> None:
    response = client.post("/questions/generate", json=PERCENTAGES_REQUEST)

    assert response.status_code == 200
    body = response.json()
    assert body["correct_answer"] in body["options"]
    assert body["question_type"] == "MCQ"


def test_generate_batch_returns_requested_count() -> None:
    response = client.post(
        "/questions/generate-batch", json={**PERCENTAGES_REQUEST, "count": 5}
    )

    assert response.status_code == 200
    questions = response.json()["questions"]
    assert len(questions) == 5
    assert all(question["correct_answer"] in question["options"] for question in questions)


def test_invalid_generation_input_is_rejected() -> None:
    response = client.post(
        "/questions/generate",
        json={**PERCENTAGES_REQUEST, "section": "Quant"},
    )

    assert response.status_code == 422


def test_unsupported_topic_combination_is_rejected() -> None:
    response = client.post(
        "/questions/generate",
        json={**PERCENTAGES_REQUEST, "subtopic": "Logarithms"},
    )

    assert response.status_code == 422


def test_batch_count_limit_is_enforced() -> None:
    response = client.post(
        "/questions/generate-batch", json={**PERCENTAGES_REQUEST, "count": 21}
    )

    assert response.status_code == 422
