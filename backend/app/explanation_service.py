"""Verified, student-facing explanations for answered practice questions."""

import re
from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .llm_provider import LLMProvider, LLMProviderError, configured_llm_provider
from .models import PracticeSession, Question, SessionQuestion
from .schemas import ExplanationDraft, ExplanationResponse


def _options(question: Question) -> dict[str, str]:
    return {
        "A": question.option_a or "",
        "B": question.option_b or "",
        "C": question.option_c or "",
        "D": question.option_d or "",
    }


def answer_label(question: Question) -> str:
    """Return the label whose option text is the stored verified answer."""
    for label, value in _options(question).items():
        if value == question.correct_answer:
            return label
    raise HTTPException(status_code=422, detail="Question has an invalid stored answer")


def _number(value: str) -> int | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return int(match.group()) if match and "." not in match.group() else None


def independently_calculate(question_text: str) -> str | None:
    """Calculate answers for the deterministic numerical templates."""
    patterns: list[tuple[str, Callable[[re.Match[str]], int]]] = [
        (r"costs Rs\. (\d+).*increased by (\d+)%", lambda m: int(m[1]) * (100 + int(m[2])) // 100),
        (r"cost for an item is Rs\. (\d+).*profit of (\d+)%", lambda m: int(m[1]) * (100 + int(m[2])) // 100),
        (r"buys an item for Rs\. (\d+).*profit of (\d+)%", lambda m: int(m[1]) * (100 + int(m[2])) // 100),
        (r"ratio of red to blue tokens is (\d+):(\d+).*?(\d+) tokens", lambda m: int(m[1]) * int(m[3]) // (int(m[1]) + int(m[2]))),
        (r"average of (\d+) numbers is (\d+).*sum of \d+ of them is (\d+)", lambda m: int(m[1]) * int(m[2]) - int(m[3])),
        (r"in (\d+) days.*in (\d+) days.*how many days", lambda m: int(m[1]) * int(m[2]) // (int(m[1]) + int(m[2]))),
        (r"at (\d+) km/h for (\d+) hours", lambda m: int(m[1]) * int(m[2])),
        (r"Solve for x: 3x \+ (\d+) = (\d+)", lambda m: (int(m[2]) - int(m[1])) // 3),
        (r"remainder when (\d+) is divided by (\d+)", lambda m: int(m[1]) % int(m[2])),
        (r"distributed equally among (\d+) clubs", lambda m: 12 // int(m[1])),
        (r"each of four teams plays.*How many matches", lambda m: 6),
    ]
    for pattern, calculation in patterns:
        match = re.search(pattern, question_text, re.IGNORECASE)
        if match:
            return str(calculation(match))
    return None


def _verify_stored_answer(question: Question) -> None:
    expected = independently_calculate(question.question_text)
    if expected is not None and expected not in question.correct_answer.replace(",", ""):
        raise HTTPException(status_code=422, detail="Stored answer failed independent verification")


def _steps_from_stored_explanation(explanation: str | None) -> list[str]:
    steps = [part.strip() for part in re.split(r"(?<=[.!?])\s+", explanation or "") if part.strip()]
    return steps or ["Use the information in the question and compare the resulting value with the options."]


def _common_mistake(question: Question, selected_answer: str | None, correct_label: str) -> str:
    if selected_answer and selected_answer != correct_label:
        return f"You selected {selected_answer}. Recheck the operation and compare your result with option {correct_label}; this is a normal place to make a quick calculation slip."
    return "A common mistake is to choose a nearby option before checking each condition in the question."


def deterministic_explanation(question: Question, selected_answer: str | None = None) -> ExplanationResponse:
    _verify_stored_answer(question)
    correct_label = answer_label(question)
    result = None if selected_answer is None else ("correct" if selected_answer == correct_label else "incorrect")
    return ExplanationResponse(
        question_id=question.id,
        correct_answer=correct_label,
        short_answer=f"The answer is {question.correct_answer} (option {correct_label}).",
        concept=question.subtopic or question.topic,
        approach=f"Identify the key {question.topic.lower()} relationship, apply it to the values in the question, and match the result to the options.",
        steps=_steps_from_stored_explanation(question.explanation),
        shortcut="Use the direct relationship shown in the solution, then estimate the result before selecting an option.",
        common_mistake=_common_mistake(question, selected_answer, correct_label),
        difficulty_note=f"This is a {question.difficulty.lower()}-level {question.topic} problem because it requires focused application of the stated information.",
        selected_answer=selected_answer,
        result=result,
    )


def _draft_references_question(question: Question, draft: ExplanationDraft) -> bool:
    text = " ".join([draft.short_answer, draft.approach, *draft.steps, draft.common_mistake]).lower()
    correct_label = answer_label(question).lower()
    expected = independently_calculate(question.question_text)
    if expected is not None and expected not in text:
        return False
    if not re.search(rf"\boption\s*{re.escape(correct_label)}\b", text) and question.correct_answer.lower() not in text:
        return False
    question_terms = [term.lower() for term in re.findall(r"[A-Za-z]{4,}", question.question_text)]
    return any(term in text for term in question_terms)


def _from_draft(question: Question, draft: ExplanationDraft, selected_answer: str | None) -> ExplanationResponse:
    correct_label = answer_label(question)
    result = None if selected_answer is None else ("correct" if selected_answer == correct_label else "incorrect")
    mistake = draft.common_mistake
    if result == "incorrect":
        mistake = f"You selected {selected_answer}. {mistake}"
    return ExplanationResponse(
        question_id=question.id,
        correct_answer=correct_label,
        selected_answer=selected_answer,
        result=result,
        **draft.model_dump(exclude={"common_mistake"}),
        common_mistake=mistake,
    )


def _provider_payload(question: Question) -> dict[str, str]:
    return {
        "question_text": question.question_text,
        **_options(question),
        "correct_answer": answer_label(question),
        "topic": question.topic,
        "subtopic": question.subtopic or "General",
        "difficulty": question.difficulty,
    }


def _authorized_question(db: Session, question_id: int) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    answered = (
        db.query(SessionQuestion)
        .join(PracticeSession, SessionQuestion.session_id == PracticeSession.id)
        .filter(SessionQuestion.question_id == question_id, SessionQuestion.selected_answer.is_not(None))
        .first()
    )
    if answered is None:
        raise HTTPException(status_code=403, detail="Answer the question before requesting an explanation")
    return question


def explain_question(
    db: Session,
    question_id: int,
    selected_answer: str | None = None,
    *,
    provider: LLMProvider | None = None,
) -> ExplanationResponse:
    question = _authorized_question(db, question_id)
    _verify_stored_answer(question)
    if selected_answer is None:
        latest = (
            db.query(SessionQuestion)
            .filter(SessionQuestion.question_id == question_id, SessionQuestion.selected_answer.is_not(None))
            .order_by(SessionQuestion.answered_at.desc())
            .first()
        )
        selected_answer = latest.selected_answer if latest else None
    selected_answer = selected_answer.upper() if selected_answer else None
    selected_provider = provider or configured_llm_provider()
    if selected_provider is not None:
        try:
            draft = selected_provider.generate_explanation(_provider_payload(question))
            if _draft_references_question(question, draft):
                return _from_draft(question, draft, selected_answer)
        except (LLMProviderError, ValueError, TypeError):
            pass
    return deterministic_explanation(question, selected_answer)