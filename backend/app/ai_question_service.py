"""LLM-first original question generation with validated template fallback."""

from fastapi import HTTPException

from .blueprint_service import generate_blueprint
from .llm_provider import LLMProvider, LLMProviderError, configured_llm_provider
from .question_generator import generate_question
from .question_validator import validate_generated_question
from .schemas import AIQuestionResponse, QuestionGenerationRequest


MAX_AI_REGENERATION_ATTEMPTS = 3


def _validated_with_provider(
    request: QuestionGenerationRequest,
    provider: LLMProvider,
    max_attempts: int,
) -> AIQuestionResponse:
    blueprint = generate_blueprint(request)
    last_validation = None
    for _ in range(max_attempts):
        try:
            question = provider.generate_question(blueprint)
        except LLMProviderError:
            raise
        validation = validate_generated_question(question, blueprint)
        last_validation = validation
        if validation.valid:
            return AIQuestionResponse(
                question=question,
                blueprint=blueprint,
                generator="llm",
                validation=validation,
            )
    errors = ", ".join(last_validation.errors if last_validation else ["unknown_error"])
    raise LLMProviderError(
        f"LLM question failed validation after {max_attempts} attempts: {errors}"
    )


def generate_ai_question(
    request: QuestionGenerationRequest,
    *,
    provider: LLMProvider | None = None,
    max_attempts: int = MAX_AI_REGENERATION_ATTEMPTS,
) -> AIQuestionResponse:
    """Use LLM generation when configured; otherwise use the validated template fallback."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    selected_provider = provider or configured_llm_provider()
    if selected_provider is not None:
        try:
            return _validated_with_provider(request, selected_provider, max_attempts)
        except LLMProviderError:
            pass

    from .validated_question_service import generate_validated_question

    try:
        fallback = generate_validated_question(request, max_attempts=max_attempts)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Question generation is temporarily unavailable",
        ) from error
    return AIQuestionResponse(
        question=fallback.question,
        blueprint=fallback.blueprint,
        generator="template",
        validation=fallback.validation,
    )