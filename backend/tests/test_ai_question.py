"""Offline tests for provider-backed original question generation."""

import json

import pytest
from fastapi.testclient import TestClient

from app.ai_question_service import generate_ai_question
from app.blueprint_service import generate_blueprint
from app.llm_provider import (
    LLMProvider,
    LLMProviderError,
    LLMSettings,
    _extract_json_payload,
)
from app.main import app
from app.prompt_builder import build_question_prompt
from app.question_generator import generate_question
from app.schemas import GeneratedQuestion, QuestionGenerationRequest


client = TestClient(app)
REQUEST = QuestionGenerationRequest(
    section="QA",
    topic="Arithmetic",
    subtopic="Percentages",
    difficulty="Medium",
    question_type="MCQ",
)


class FakeProvider(LLMProvider):
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def generate_question(self, blueprint):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_prompt_contains_blueprint_only_and_originality_constraints() -> None:
    prompt = build_question_prompt(generate_blueprint(REQUEST))

    assert "successive_percentage_change" in prompt
    assert "expected_time_seconds: 120" in prompt
    assert "ORIGINAL" in prompt
    assert "Do not copy, quote, paraphrase" in prompt
    assert "known CAT question" in prompt


def test_structured_response_parser_accepts_openai_compatible_json() -> None:
    question = generate_question(REQUEST).model_dump()
    payload = {"choices": [{"message": {"content": json.dumps(question)}}]}

    assert _extract_json_payload(payload) == question


def test_structured_response_parser_rejects_malformed_json() -> None:
    with pytest.raises(LLMProviderError, match="not valid JSON"):
        _extract_json_payload({"choices": [{"message": {"content": "not-json"}}]})


def test_valid_llm_response_uses_llm_generator() -> None:
    provider = FakeProvider([generate_question(REQUEST)])

    result = generate_ai_question(REQUEST, provider=provider)

    assert result.generator == "llm"
    assert result.validation.valid is True
    assert provider.calls == 1


def test_validator_rejection_regenerates_with_same_provider() -> None:
    valid = generate_question(REQUEST)
    invalid = valid.model_copy(update={"options": valid.options[:3]})
    provider = FakeProvider([invalid, valid])

    result = generate_ai_question(REQUEST, provider=provider, max_attempts=2)

    assert result.generator == "llm"
    assert result.validation.valid is True
    assert provider.calls == 2


def test_maximum_retry_behavior_falls_back_after_llm_rejections() -> None:
    valid = generate_question(REQUEST)
    invalid = valid.model_copy(update={"options": valid.options[:3]})
    provider = FakeProvider([invalid, invalid, invalid])

    result = generate_ai_question(REQUEST, provider=provider, max_attempts=3)

    assert result.generator == "template"
    assert result.validation.valid is True
    assert provider.calls == 3


def test_provider_error_falls_back_to_template() -> None:
    provider = FakeProvider([LLMProviderError("timeout")])

    result = generate_ai_question(REQUEST, provider=provider)

    assert result.generator == "template"
    assert result.validation.valid is True


def test_missing_api_key_uses_template_fallback(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    result = generate_ai_question(REQUEST)

    assert result.generator == "template"
    assert result.validation.valid is True


def test_provider_settings_never_leak_credentials() -> None:
    settings = LLMSettings(
        api_key="secret-test-key",
        model="test-model",
        base_url="https://example.invalid",
    )
    result = generate_ai_question(REQUEST, provider=FakeProvider([generate_question(REQUEST)]))
    response_text = result.model_dump_json()

    assert settings.api_key not in response_text
    assert "LLM_API_KEY" not in response_text


def test_generate_ai_endpoint_returns_generator_and_validation() -> None:
    response = client.post("/questions/generate-ai", json=REQUEST.model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["generator"] == "template"
    assert body["validation"]["valid"] is True
    assert "LLM_API_KEY" not in json.dumps(body)