"""Provider abstraction and environment-configured structured-output client."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .prompt_builder import build_question_prompt
from .schemas import GeneratedQuestion, QuestionBlueprint


class LLMProviderError(RuntimeError):
    """Raised for unavailable, malformed, or failed provider responses."""


class LLMProvider(ABC):
    """Interface used by the question-generation pipeline."""

    @abstractmethod
    def generate_question(self, blueprint: QuestionBlueprint) -> GeneratedQuestion:
        """Generate one structured original question."""


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 20.0

    @classmethod
    def from_environment(cls) -> "LLMSettings | None":
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            model=os.getenv("LLM_MODEL", "").strip() or "configured-model",
            base_url=os.getenv("LLM_BASE_URL", "").strip().rstrip("/"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
        )


def _extract_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract a JSON object from common OpenAI-compatible response shapes."""
    if "question_text" in payload:
        return payload
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMProviderError("LLM response did not contain choices")
    content = choices[0].get("message", {}).get("content")
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    if not isinstance(content, str):
        raise LLMProviderError("LLM response did not contain structured content")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise LLMProviderError("LLM response was not valid JSON") from error
    if not isinstance(parsed, dict):
        raise LLMProviderError("LLM JSON response was not an object")
    return parsed


class EnvironmentLLMProvider(LLMProvider):
    """Small OpenAI-compatible JSON client configured exclusively by environment."""

    def __init__(self, settings: LLMSettings):
        if not settings.base_url:
            raise LLMProviderError("LLM_BASE_URL is not configured")
        self.settings = settings

    def generate_question(self, blueprint: QuestionBlueprint) -> GeneratedQuestion:
        body = {
            "model": self.settings.model,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the requested schema."},
                {"role": "user", "content": build_question_prompt(blueprint)},
            ],
            "response_format": {"type": "json_object"},
        }
        request = Request(
            f"{self.settings.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise LLMProviderError("LLM provider request failed") from error
        try:
            return GeneratedQuestion.model_validate(_extract_json_payload(response_payload))
        except (TypeError, ValueError) as error:
            raise LLMProviderError("LLM response did not match the question schema") from error


def configured_llm_provider() -> LLMProvider | None:
    """Return a configured provider or None without exposing configuration details."""
    settings = LLMSettings.from_environment()
    if settings is None or not settings.base_url:
        return None
    try:
        return EnvironmentLLMProvider(settings)
    except LLMProviderError:
        return None