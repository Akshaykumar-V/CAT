"""Blueprint, generation, validation, and bounded regeneration pipeline."""

from collections.abc import Callable

from fastapi import HTTPException

from .blueprint_service import generate_blueprint
from .question_generator import generate_question
from .question_validator import validate_generated_question
from .schemas import (
    GeneratedQuestion,
    QuestionGenerationRequest,
    ValidatedQuestionResponse,
)


MAX_REGENERATION_ATTEMPTS = 3
QuestionGenerator = Callable[[QuestionGenerationRequest], GeneratedQuestion]


class ValidationExhaustedError(ValueError):
    """Raised when bounded regeneration cannot produce a valid question."""


def generate_validated_question(
    request: QuestionGenerationRequest,
    *,
    max_attempts: int = MAX_REGENERATION_ATTEMPTS,
    generator: QuestionGenerator = generate_question,
) -> ValidatedQuestionResponse:
    """Generate against one blueprint and retry invalid output a finite number of times."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    blueprint = generate_blueprint(request)
    last_validation = None
    for _ in range(max_attempts):
        question = generator(request)
        validation = validate_generated_question(question, blueprint)
        last_validation = validation
        if validation.valid:
            return ValidatedQuestionResponse(
                question=question,
                blueprint=blueprint,
                validation=validation,
            )
    raise ValidationExhaustedError(
        f"Question failed validation after {max_attempts} attempts: "
        f"{', '.join(last_validation.errors if last_validation else ['unknown_error'])}"
    )


def generate_validated_question_or_http(
    request: QuestionGenerationRequest,
) -> ValidatedQuestionResponse:
    """Translate exhausted generation into a clear API error."""
    try:
        return generate_validated_question(request)
    except ValidationExhaustedError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error