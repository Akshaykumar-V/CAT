"""Tests for question blueprints, validation, and bounded regeneration."""

import pytest
from fastapi.testclient import TestClient

from app.blueprint_service import BLUEPRINT_RULES, generate_blueprint
from app.main import app
from app.question_generator import TEMPLATES, generate_question
from app.question_validator import validate_generated_question
from app.schemas import QuestionGenerationRequest
from app.validated_question_service import (
    ValidationExhaustedError,
    generate_validated_question,
)


client = TestClient(app)
BASE_REQUEST = {
    "section": "QA",
    "topic": "Arithmetic",
    "subtopic": "Percentages",
    "difficulty": "Medium",
    "question_type": "MCQ",
}


def request_for(**changes) -> QuestionGenerationRequest:
    return QuestionGenerationRequest(**{**BASE_REQUEST, **changes})


def test_blueprint_generation_has_controlled_structure() -> None:
    blueprint = generate_blueprint(request_for())

    assert blueprint.section == "QA"
    assert blueprint.concepts == ["successive_percentage_change", "reverse_percentage"]
    assert blueprint.number_of_steps >= 1
    assert blueprint.reasoning_level == "medium"
    assert blueprint.expected_time_seconds == 120


def test_blueprint_exists_for_every_supported_section_and_template() -> None:
    assert set(BLUEPRINT_RULES) == set(TEMPLATES)
    for section, topic, subtopic in TEMPLATES:
        blueprint = generate_blueprint(
            request_for(section=section, topic=topic, subtopic=subtopic)
        )
        assert blueprint.section == section
        assert blueprint.subtopic == subtopic


def test_difficulty_changes_blueprint_complexity() -> None:
    easy = generate_blueprint(request_for(difficulty="Easy"))
    medium = generate_blueprint(request_for(difficulty="Medium"))
    hard = generate_blueprint(request_for(difficulty="Hard"))

    assert easy.reasoning_level == "low"
    assert medium.reasoning_level == "medium"
    assert hard.reasoning_level == "high"
    assert easy.number_of_steps < medium.number_of_steps < hard.number_of_steps
    assert easy.expected_time_seconds < medium.expected_time_seconds < hard.expected_time_seconds


def test_validated_generation_returns_question_blueprint_and_checks() -> None:
    result = generate_validated_question(request_for())

    assert result.validation.valid is True
    assert result.validation.checks_passed
    assert result.question.correct_answer in result.question.options
    assert result.blueprint.subtopic == "Percentages"


def test_validator_rejects_missing_option() -> None:
    question = generate_question(request_for()).model_dump()
    question["options"] = question["options"][:3]

    result = validate_generated_question(question, generate_blueprint(request_for()))

    assert result.valid is False
    assert "required_options_missing" in result.errors


def test_validator_rejects_duplicate_options() -> None:
    question = generate_question(request_for()).model_dump()
    question["options"][1] = question["options"][0]

    result = validate_generated_question(question, generate_blueprint(request_for()))

    assert result.valid is False
    assert "duplicate_options" in result.errors


def test_validator_rejects_invalid_correct_answer() -> None:
    question = generate_question(request_for()).model_dump()
    question["correct_answer"] = "Not an option"

    result = validate_generated_question(question, generate_blueprint(request_for()))

    assert result.valid is False
    assert "no_correct_option" in result.errors


def test_validator_rejects_multiple_correct_answers() -> None:
    question = generate_question(request_for()).model_dump()
    duplicate_index = next(
        index
        for index, option in enumerate(question["options"])
        if option != question["correct_answer"]
    )
    question["options"][duplicate_index] = question["correct_answer"]

    result = validate_generated_question(question, generate_blueprint(request_for()))

    assert result.valid is False
    assert "multiple_correct_options" in result.errors


def test_validator_rejects_no_correct_answers() -> None:
    question = generate_question(request_for()).model_dump()
    question["correct_answer"] = "No matching answer"

    result = validate_generated_question(question, generate_blueprint(request_for()))

    assert result.valid is False
    assert "no_correct_option" in result.errors


def test_validator_rejects_unsupported_numerical_answer() -> None:
    question = generate_question(request_for()).model_dump()
    question["correct_answer"] = "9999"
    question["options"][0] = "9999"

    result = validate_generated_question(question, generate_blueprint(request_for()))

    assert result.valid is False
    assert "numerical_answer_not_supported_by_explanation" in result.errors


def test_regeneration_retries_after_validation_failure() -> None:
    valid = generate_question(request_for())
    invalid = valid.model_copy(update={"options": valid.options[:3]})
    generated = iter([invalid, valid])
    attempts = 0

    def generator(_request):
        nonlocal attempts
        attempts += 1
        return next(generated)

    result = generate_validated_question(request_for(), generator=generator, max_attempts=2)

    assert result.validation.valid is True
    assert attempts == 2


def test_regeneration_stops_at_maximum_attempts() -> None:
    valid = generate_question(request_for())
    invalid = valid.model_copy(update={"options": valid.options[:3]})
    attempts = 0

    def generator(_request):
        nonlocal attempts
        attempts += 1
        return invalid

    with pytest.raises(ValidationExhaustedError, match="after 3 attempts"):
        generate_validated_question(request_for(), generator=generator, max_attempts=3)
    assert attempts == 3


def test_blueprint_and_validated_generation_endpoints() -> None:
    blueprint_response = client.post("/questions/blueprint", json=BASE_REQUEST)
    validated_response = client.post("/questions/generate-validated", json=BASE_REQUEST)

    assert blueprint_response.status_code == 200
    assert blueprint_response.json()["subtopic"] == "Percentages"
    assert validated_response.status_code == 200
    assert validated_response.json()["validation"]["valid"] is True