"""Deterministic quality checks for generated original questions."""

import re
from typing import Any

from .schemas import GeneratedQuestion, QuestionBlueprint, QuestionValidation


def _append_check(result: QuestionValidation, check: str) -> None:
    result.checks_passed.append(check)


def _raw_question(question: GeneratedQuestion | dict[str, Any]) -> dict[str, Any]:
    if isinstance(question, GeneratedQuestion):
        return question.model_dump()
    return question


def _validate_metadata(
    result: QuestionValidation,
    question: dict[str, Any],
    blueprint: QuestionBlueprint,
) -> None:
    for field in ("section", "topic", "subtopic", "question_type", "difficulty"):
        if question.get(field) != getattr(blueprint, field):
            result.errors.append(f"metadata_mismatch:{field}")
    if not result.errors or not any(item.startswith("metadata_mismatch") for item in result.errors):
        _append_check(result, "metadata_valid")


def _validate_numeric_content(
    result: QuestionValidation,
    question: dict[str, Any],
    blueprint: QuestionBlueprint,
) -> None:
    if blueprint.section != "QA":
        return
    text = f"{question.get('question_text', '')} {question.get('explanation', '')}".lower()
    if re.search(r"(?:divide|divided|division)[^.!?]{0,30}\b0\b|/\s*0\b", text):
        result.errors.append("numerical_division_by_zero")
    if re.search(r"\b(?:impossible|contradictory|no solution)\b", text):
        result.errors.append("numerical_contradiction")
    answer = str(question.get("correct_answer", ""))
    numeric_tokens = re.findall(r"-?\d+(?:\.\d+)?", answer)
    if numeric_tokens and not any(token in str(question.get("explanation", "")) for token in numeric_tokens):
        result.errors.append("numerical_answer_not_supported_by_explanation")
    else:
        _append_check(result, "numerical_consistency_checked")


def _validate_difficulty(
    result: QuestionValidation,
    question: dict[str, Any],
    blueprint: QuestionBlueprint,
) -> None:
    text = str(question.get("question_text", ""))
    if blueprint.difficulty == "Easy" and blueprint.number_of_steps > 3:
        result.warnings.append("easy_blueprint_has_more_than_three_steps")
    if blueprint.difficulty == "Hard" and blueprint.number_of_steps >= 4 and len(text.split()) < 12:
        result.warnings.append("hard_question_may_be_too_short_for_blueprint")
    _append_check(result, "difficulty_profile_reviewed")


def validate_generated_question(
    question: GeneratedQuestion | dict[str, Any],
    blueprint: QuestionBlueprint,
) -> QuestionValidation:
    """Return all deterministic quality findings without raising on bad output."""
    raw = _raw_question(question)
    result = QuestionValidation(valid=False)
    question_text = str(raw.get("question_text", "")).strip()
    options = raw.get("options")
    correct_answer = raw.get("correct_answer")
    explanation = str(raw.get("explanation", "")).strip()

    if question_text:
        _append_check(result, "question_text_present")
    else:
        result.errors.append("question_text_empty")
    if correct_answer is not None and str(correct_answer).strip():
        _append_check(result, "correct_answer_present")
    else:
        result.errors.append("correct_answer_missing")
    if isinstance(options, list) and len(options) == 4 and all(str(option).strip() for option in options):
        _append_check(result, "four_options_present")
    else:
        result.errors.append("required_options_missing")
    if isinstance(options, list) and len(options) == len(set(map(str, options))):
        _append_check(result, "options_unique")
    else:
        result.errors.append("duplicate_options")
    if explanation:
        _append_check(result, "explanation_present")
    else:
        result.errors.append("explanation_missing")

    if isinstance(options, list) and correct_answer is not None:
        correct_count = sum(option == correct_answer for option in options)
        if correct_count == 1:
            _append_check(result, "exactly_one_correct_option")
        elif correct_count > 1:
            result.errors.append("multiple_correct_options")
        else:
            result.errors.append("no_correct_option")

    _validate_metadata(result, raw, blueprint)
    _validate_numeric_content(result, raw, blueprint)
    _validate_difficulty(result, raw, blueprint)
    result.valid = not result.errors
    return result