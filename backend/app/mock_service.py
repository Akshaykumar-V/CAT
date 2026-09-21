"""Server-authoritative CAT mock sessions built on the existing question catalog."""

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .explanation_service import answer_label, deterministic_explanation
from .models import MockConfiguration, MockSession, MockSessionQuestion, Question
from .question_generator import TEMPLATES
from .schemas import (
    MockAnswerRequest,
    MockConfigurationResponse,
    MockDifficultyResult,
    MockQuestionResponse,
    MockResultResponse,
    MockReviewQuestionResponse,
    MockReviewResponse,
    MockSectionResult,
    MockSessionResponse,
    MockStartRequest,
    MockTopicResult,
    QuestionGenerationRequest,
)
from .validated_question_service import generate_validated_question_or_http


DEFAULT_MOCK_ID = "cat-v2-mock-1"
DEFAULT_MOCK = {
    "mock_id": DEFAULT_MOCK_ID,
    "title": "CAT Full Mock 01",
    "sections": {"VARC": 3, "DILR": 3, "QA": 3},
    "section_order": ["VARC", "DILR", "QA"],
    "section_time_limit": {"VARC": 900, "DILR": 900, "QA": 900},
    "status": "NOT_STARTED",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _total_questions(config: MockConfiguration) -> int:
    return sum(int(value) for value in config.sections.values())


def _total_time(config: MockConfiguration) -> int:
    return sum(int(config.section_time_limit[section]) for section in config.section_order)


def _ensure_default_config(db: Session) -> MockConfiguration:
    config = db.get(MockConfiguration, DEFAULT_MOCK_ID)
    if config is None:
        config = MockConfiguration(
            mock_id=DEFAULT_MOCK["mock_id"],
            title=DEFAULT_MOCK["title"],
            total_questions=_total_questions_from_definition(DEFAULT_MOCK),
            sections=DEFAULT_MOCK["sections"],
            section_order=DEFAULT_MOCK["section_order"],
            section_time_limit=DEFAULT_MOCK["section_time_limit"],
            total_time_limit=_total_time_from_definition(DEFAULT_MOCK),
            question_ids=[],
            status=DEFAULT_MOCK["status"],
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _total_questions_from_definition(definition: dict[str, object]) -> int:
    return sum(int(value) for value in definition["sections"].values())


def _total_time_from_definition(definition: dict[str, object]) -> int:
    return sum(int(definition["section_time_limit"][section]) for section in definition["section_order"])


def list_mocks(db: Session) -> list[MockConfigurationResponse]:
    _ensure_default_config(db)
    return [_configuration_response(config) for config in db.query(MockConfiguration).order_by(MockConfiguration.mock_id).all()]


def get_mock_configuration(db: Session, mock_id: str) -> MockConfiguration:
    if mock_id == DEFAULT_MOCK_ID:
        _ensure_default_config(db)
    config = db.get(MockConfiguration, mock_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Mock configuration not found")
    return config


def _configuration_response(config: MockConfiguration) -> MockConfigurationResponse:
    return MockConfigurationResponse(
        mock_id=config.mock_id,
        title=config.title,
        total_questions=config.total_questions,
        sections=config.sections,
        section_order=config.section_order,
        section_time_limit=config.section_time_limit,
        total_time_limit=config.total_time_limit,
        question_ids=config.question_ids or [],
        status=config.status,
    )


def _question_options(question: Question) -> dict[str, str]:
    return {"A": question.option_a or "", "B": question.option_b or "", "C": question.option_c or "", "D": question.option_d or ""}


def _save_generated_question(db: Session, generated) -> Question:
    question = Question(
        section=generated.section,
        topic=generated.topic,
        subtopic=generated.subtopic,
        difficulty=generated.difficulty,
        question_type=generated.question_type,
        question_text=generated.question_text,
        option_a=generated.options[0],
        option_b=generated.options[1],
        option_c=generated.options[2],
        option_d=generated.options[3],
        correct_answer=generated.correct_answer,
        explanation=generated.explanation,
        source="Validated original mock question",
    )
    db.add(question)
    db.flush()
    return question


def _build_question_pool(db: Session, config: MockConfiguration) -> list[int]:
    required_ids = list(config.question_ids or [])
    questions_by_section: dict[str, list[Question]] = defaultdict(list)
    for question_id in required_ids:
        question = db.get(Question, question_id)
        if question is not None:
            questions_by_section[question.section].append(question)

    for section in config.section_order:
        required = int(config.sections[section])
        existing = questions_by_section[section]
        if len(existing) >= required:
            continue
        known_ids = {question.id for question in existing}
        for question in db.query(Question).filter(Question.section == section).order_by(Question.id).all():
            if question.id not in known_ids:
                existing.append(question)
                known_ids.add(question.id)
            if len(existing) >= required:
                break
        template_keys = [key for key in TEMPLATES if key[0] == section]
        while len(existing) < required:
            key = template_keys[len(existing) % len(template_keys)]
            generated = generate_validated_question_or_http(
                QuestionGenerationRequest(
                    section=key[0], topic=key[1], subtopic=key[2], difficulty="Medium", question_type="MCQ"
                )
            )
            existing.append(_save_generated_question(db, generated.question))
        required_ids.extend(question.id for question in existing if question.id not in required_ids)

    config.question_ids = required_ids
    config.total_questions = _total_questions(config)
    config.total_time_limit = _total_time(config)
    db.commit()
    return required_ids


def _total_questions(config: MockConfiguration) -> int:
    return sum(int(config.sections[section]) for section in config.section_order)


def _session_questions(db: Session, session_id: int) -> list[tuple[MockSessionQuestion, Question]]:
    return (db.query(MockSessionQuestion, Question)
            .join(Question, MockSessionQuestion.question_id == Question.id)
            .filter(MockSessionQuestion.mock_session_id == session_id)
            .order_by(MockSessionQuestion.question_order).all())


def _current_section(config: MockConfiguration, session: MockSession) -> str | None:
    if session.current_section_index >= len(config.section_order):
        return None
    return config.section_order[session.current_section_index]


def _section_elapsed(session: MockSession, now: datetime | None = None) -> int:
    return max(0, int(((now or utc_now()) - as_utc(session.section_started_at)).total_seconds()))


def _total_elapsed(session: MockSession, now: datetime | None = None) -> int:
    return max(0, int(((now or utc_now()) - as_utc(session.started_at)).total_seconds()))


def _record_section_time(config: MockConfiguration, session: MockSession, now: datetime) -> None:
    section = _current_section(config, session)
    if section is not None:
        used = min(_section_elapsed(session, now), int(config.section_time_limit[section]))
        section_time = dict(session.section_time_used or {})
        section_time[section] = used
        session.section_time_used = section_time


def _advance_section(db: Session, config: MockConfiguration, session: MockSession, now: datetime) -> None:
    _record_section_time(config, session, now)
    session.current_section_index += 1
    if session.current_section_index >= len(config.section_order):
        session.status = "COMPLETED"
        session.finished_at = now
    else:
        session.status = "IN_PROGRESS"
        session.section_started_at = now
    db.commit()
    db.refresh(session)


def _refresh_state(db: Session, config: MockConfiguration, session: MockSession) -> MockSession:
    if session.status == "SECTION_COMPLETE":
        _advance_section(db, config, session, utc_now())
    elif session.status == "IN_PROGRESS":
        now = utc_now()
        section = _current_section(config, session)
        if _total_elapsed(session, now) >= config.total_time_limit or (section and _section_elapsed(session, now) >= config.section_time_limit[section]):
            _advance_section(db, config, session, now)
    return session


def _to_question_response(row: MockSessionQuestion, question: Question) -> MockQuestionResponse:
    return MockQuestionResponse(
        question_id=question.id,
        question_order=row.question_order,
        section=row.section,
        topic=question.topic,
        subtopic=question.subtopic,
        difficulty=question.difficulty,
        question_text=question.question_text,
        options=_question_options(question),
        answered=row.selected_answer is not None,
        selected_answer=row.selected_answer,
        marked_for_review=bool(row.marked_for_review),
    )


def _to_session_response(db: Session, config: MockConfiguration, session: MockSession) -> MockSessionResponse:
    section = _current_section(config, session)
    rows = [(row, question) for row, question in _session_questions(db, session.id) if section is None or row.section == section]
    remaining = 0
    if session.status == "IN_PROGRESS" and section:
        remaining = max(0, min(int(config.section_time_limit[section]) - _section_elapsed(session), config.total_time_limit - _total_elapsed(session)))
    return MockSessionResponse(
        id=session.id,
        mock_id=config.mock_id,
        title=config.title,
        status=session.status,
        current_section=section,
        section_order=config.section_order,
        section_remaining_seconds=remaining,
        total_elapsed_seconds=min(_total_elapsed(session), config.total_time_limit),
        total_time_limit=config.total_time_limit,
        questions=[_to_question_response(row, question) for row, question in rows],
    )


def start_mock(db: Session, request: MockStartRequest) -> MockSessionResponse:
    config = get_mock_configuration(db, request.mock_id)
    question_ids = _build_question_pool(db, config)
    ordered_ids: list[tuple[str, int]] = []
    cursor = 0
    for section in config.section_order:
        count = int(config.sections[section])
        for question_id in question_ids[cursor:cursor + count]:
            ordered_ids.append((section, question_id))
        cursor += count
    if len(ordered_ids) != config.total_questions:
        raise HTTPException(status_code=503, detail="Mock question pool is unavailable")

    now = utc_now()
    session = MockSession(
        mock_id=config.mock_id,
        status="IN_PROGRESS",
        started_at=now,
        section_started_at=now,
        current_section_index=0,
        section_time_used={},
    )
    db.add(session)
    db.flush()
    for order, (section, question_id) in enumerate(ordered_ids, start=1):
        db.add(MockSessionQuestion(mock_session_id=session.id, question_id=question_id, section=section, question_order=order))
    config.status = "IN_PROGRESS"
    db.commit()
    db.refresh(session)
    return _to_session_response(db, config, session)


def get_mock_session(db: Session, session_id: int) -> MockSessionResponse:
    session = db.get(MockSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mock session not found")
    config = get_mock_configuration(db, session.mock_id)
    session = _refresh_state(db, config, session)
    return _to_session_response(db, config, session)


def answer_mock_question(db: Session, session_id: int, request: MockAnswerRequest) -> MockSessionResponse:
    session = db.get(MockSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mock session not found")
    config = get_mock_configuration(db, session.mock_id)
    session = _refresh_state(db, config, session)
    if session.status != "IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Mock session is not accepting answers")
    section = _current_section(config, session)
    result = (db.query(MockSessionQuestion, Question)
              .join(Question, MockSessionQuestion.question_id == Question.id)
              .filter(MockSessionQuestion.mock_session_id == session_id, MockSessionQuestion.question_id == request.question_id, MockSessionQuestion.section == section)
              .first())
    if result is None:
        raise HTTPException(status_code=404, detail="Question is not in the current mock section")
    row, question = result
    if row.selected_answer is not None and request.selected_answer is not None:
        raise HTTPException(status_code=409, detail="Question has already been answered")
    if request.selected_answer is not None:
        row.selected_answer = request.selected_answer
        row.is_correct = request.selected_answer == answer_label(question)
        row.time_spent_seconds = request.time_spent_seconds
        row.answered_at = utc_now()
    row.marked_for_review = request.marked_for_review
    db.commit()
    return _to_session_response(db, config, session)


def submit_mock_section(db: Session, session_id: int) -> MockSessionResponse:
    session = db.get(MockSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mock session not found")
    config = get_mock_configuration(db, session.mock_id)
    session = _refresh_state(db, config, session)
    if session.status != "IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Mock section is not active")
    session.status = "SECTION_COMPLETE"
    db.commit()
    db.refresh(session)
    return _to_session_response(db, config, session)


def finish_mock(db: Session, session_id: int) -> MockResultResponse:
    session = db.get(MockSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mock session not found")
    config = get_mock_configuration(db, session.mock_id)
    if session.status in {"IN_PROGRESS", "SECTION_COMPLETE"}:
        _record_section_time(config, session, utc_now())
        session.status = "COMPLETED"
        session.finished_at = utc_now()
        db.commit()
        db.refresh(session)
    if session.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Mock session cannot be finished in its current state")
    return mock_result(db, session_id)


def _metrics(rows: list[tuple[MockSessionQuestion, Question]]) -> tuple[int, int, int, int, float]:
    attempted = [record for record in rows if record[0].selected_answer is not None]
    correct = sum(row.is_correct is True for row, _ in attempted)
    total = len(rows)
    return len(attempted), correct, len(attempted) - correct, total - len(attempted), round((correct / len(attempted)) * 100, 2) if attempted else 0.0


def mock_result(db: Session, session_id: int) -> MockResultResponse:
    session = db.get(MockSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mock session not found")
    if session.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Mock results are available after completion")
    config = get_mock_configuration(db, session.mock_id)
    rows = _session_questions(db, session_id)
    attempted, correct, incorrect, unanswered, accuracy = _metrics(rows)
    sections = []
    for section in config.section_order:
        section_rows = [(row, question) for row, question in rows if row.section == section]
        section_attempted, section_correct, section_incorrect, section_unanswered, section_accuracy = _metrics(section_rows)
        sections.append(MockSectionResult(section=section, attempted=section_attempted, correct=section_correct, incorrect=section_incorrect, unanswered=section_unanswered, accuracy=section_accuracy, time_used_seconds=int((session.section_time_used or {}).get(section, 0))))
    grouped_topics: dict[str, list[tuple[MockSessionQuestion, Question]]] = defaultdict(list)
    grouped_difficulties: dict[str, list[tuple[MockSessionQuestion, Question]]] = defaultdict(list)
    for row, question in rows:
        grouped_topics[question.topic].append((row, question))
        grouped_difficulties[question.difficulty].append((row, question))
    topics = []
    for topic, topic_rows in sorted(grouped_topics.items()):
        topic_attempted, topic_correct, _, _, topic_accuracy = _metrics(topic_rows)
        topics.append(MockTopicResult(topic=topic, attempted=topic_attempted, correct=topic_correct, accuracy=topic_accuracy))
    difficulties = []
    for difficulty, difficulty_rows in sorted(grouped_difficulties.items()):
        difficulty_attempted, difficulty_correct, _, _, difficulty_accuracy = _metrics(difficulty_rows)
        difficulties.append(MockDifficultyResult(difficulty=difficulty, attempted=difficulty_attempted, correct=difficulty_correct, accuracy=difficulty_accuracy))
    scored_sections = [item for item in sections if item.attempted]
    strongest_section = max(scored_sections, key=lambda item: item.accuracy).section if scored_sections else None
    weakest_section = min(scored_sections, key=lambda item: item.accuracy).section if scored_sections else None
    strongest_topics = [item.topic for item in topics if item.attempted and item.accuracy >= 80]
    topics_needing_practice = [item.topic for item in topics if item.attempted and item.accuracy < 60]
    observations = []
    for item in sections:
        limit = int(config.section_time_limit[item.section])
        if item.unanswered:
            observations.append(f"{item.section}: {item.unanswered} unanswered question(s).")
        if item.time_used_seconds >= limit:
            observations.append(f"{item.section}: section time was fully used.")
    return MockResultResponse(mock_session_id=session_id, status=session.status, attempted=attempted, correct=correct, incorrect=incorrect, unanswered=unanswered, accuracy=accuracy, total_time_seconds=min(_total_elapsed(session), config.total_time_limit), sections=sections, topics=topics, difficulties=difficulties, strongest_section=strongest_section, weakest_section=weakest_section, strongest_topics=strongest_topics, topics_needing_practice=topics_needing_practice, time_management_observations=observations)


def mock_review(db: Session, session_id: int) -> MockReviewResponse:
    session = db.get(MockSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mock session not found")
    if session.status != "COMPLETED":
        raise HTTPException(status_code=403, detail="Mock review is available after completion")
    questions = []
    for row, question in _session_questions(db, session_id):
        selected = row.selected_answer
        questions.append(MockReviewQuestionResponse(question_id=question.id, question_order=row.question_order, section=row.section, topic=question.topic, question_text=question.question_text, options=_question_options(question), selected_answer=selected, correct_answer=answer_label(question), is_correct=bool(row.is_correct), explanation=deterministic_explanation(question, selected)))
    return MockReviewResponse(mock_session_id=session_id, questions=questions)
