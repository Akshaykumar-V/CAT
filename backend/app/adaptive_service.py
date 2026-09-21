"""Configurable adaptive practice selection from completed practice history."""

from dataclasses import dataclass
from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import PracticeSession, Question, SessionQuestion
from .ai_question_service import generate_ai_question
from .practice_service import get_session, utc_now
from .question_generator import TEMPLATES, generate_question
from .schemas import (
    AdaptivePracticeStartRequest,
    GeneratedQuestion,
    AIQuestionResponse,
    QuestionGenerationRequest,
)


@dataclass(frozen=True)
class AdaptiveSelectionConfig:
    """The transparent knobs controlling adaptive selection."""

    recent_session_decay: float = 0.65
    maintenance_ratio: float = 0.20
    recommendation_topic_count: int = 3
    low_accuracy_difficulties: tuple[str, ...] = ("Easy", "Easy", "Medium")
    developing_difficulties: tuple[str, ...] = ("Easy", "Medium")
    strong_developing_difficulties: tuple[str, ...] = ("Medium", "Medium", "Hard")
    strong_difficulties: tuple[str, ...] = ("Medium", "Hard")


ADAPTIVE_CONFIG = AdaptiveSelectionConfig()
SECTIONS = ("VARC", "DILR", "QA")
MAX_ADAPTIVE_GENERATION_ATTEMPTS = 3


@dataclass
class TopicProfile:
    """Recent, weighted performance for one generator topic."""

    section: str
    topic: str
    subtopic: str
    attempted: float = 0.0
    correct: float = 0.0
    weighted_time: float = 0.0

    @property
    def accuracy(self) -> float | None:
        return round((self.correct / self.attempted) * 100, 2) if self.attempted else None

    @property
    def average_time_seconds(self) -> float | None:
        return round(self.weighted_time / self.attempted, 2) if self.attempted else None

    @property
    def priority(self) -> int:
        if self.accuracy is None:
            return 1
        if self.accuracy < 60:
            return 0
        if self.accuracy < 80:
            return 1
        return 2


def _template_matches(question: Question, template: tuple[str, str, str]) -> bool:
    section, topic, subtopic = template
    return question.section == section and (
        (question.topic == topic and question.subtopic == subtopic)
        or question.topic == subtopic
        or question.subtopic == subtopic
    )


def adaptive_topic_profiles(
    db: Session,
    section: str,
    config: AdaptiveSelectionConfig = ADAPTIVE_CONFIG,
) -> list[TopicProfile]:
    """Build topic profiles using exponentially lower weights for older sessions."""
    templates = [template for template in TEMPLATES if template[0] == section]
    profiles = {template: TopicProfile(*template) for template in templates}
    records = (
        db.query(SessionQuestion, Question, PracticeSession)
        .join(Question, SessionQuestion.question_id == Question.id)
        .join(PracticeSession, SessionQuestion.session_id == PracticeSession.id)
        .filter(PracticeSession.status == "completed", PracticeSession.section == section)
        .order_by(PracticeSession.finished_at.desc(), PracticeSession.id.desc())
        .all()
    )

    session_weights: dict[int, float] = {}
    for _, _, session in records:
        if session.id not in session_weights:
            session_weights[session.id] = config.recent_session_decay ** len(session_weights)

    for session_question, question, session in records:
        if session_question.selected_answer is None:
            continue
        weight = session_weights[session.id]
        for template, profile in profiles.items():
            if _template_matches(question, template):
                profile.attempted += weight
                profile.correct += weight if session_question.is_correct is True else 0
                profile.weighted_time += weight * (session_question.time_spent_seconds or 0)
                break
    return list(profiles.values())


def difficulty_options_for_accuracy(
    accuracy: float | None,
    config: AdaptiveSelectionConfig = ADAPTIVE_CONFIG,
) -> tuple[str, ...]:
    """Return the configured difficulty mix for a topic's recorded accuracy."""
    if accuracy is None or accuracy < 50:
        return config.low_accuracy_difficulties
    if accuracy < 70:
        return config.developing_difficulties
    if accuracy < 85:
        return config.strong_developing_difficulties
    return config.strong_difficulties


def _ordered_profiles(profiles: list[TopicProfile]) -> list[TopicProfile]:
    return sorted(
        profiles,
        key=lambda profile: (
            profile.priority,
            profile.accuracy if profile.accuracy is not None else -1,
            -(profile.average_time_seconds or 0),
            profile.subtopic,
        ),
    )


def _topic_plan(
    profiles: list[TopicProfile],
    question_count: int,
    config: AdaptiveSelectionConfig,
) -> list[TopicProfile]:
    ordered = _ordered_profiles(profiles)
    strong = [profile for profile in ordered if profile.priority == 2]
    priority = [profile for profile in ordered if profile.priority != 2]
    if not ordered:
        return []
    maintenance_count = (
        min(
            len(strong),
            max(1, round(question_count * config.maintenance_ratio)),
            max(0, question_count - 1),
        )
        if strong and priority
        else 0
    )
    plan: list[TopicProfile] = []
    known_priority = [profile for profile in priority if profile.attempted]
    primary = known_priority or priority or strong
    for index in range(question_count - maintenance_count):
        plan.append(primary[index % len(primary)])
    for index in range(maintenance_count):
        plan.append(strong[index % len(strong)])
    return plan


def _previously_attempted_ids(db: Session) -> set[int]:
    rows = (
        db.query(SessionQuestion.question_id)
        .join(PracticeSession, SessionQuestion.session_id == PracticeSession.id)
        .filter(PracticeSession.status == "completed")
        .all()
    )
    return {question_id for question_id, in rows}


def _profiles_with_unseen_questions(
    db: Session,
    profiles: list[TopicProfile],
    excluded_ids: set[int],
    excluded_texts: set[str],
) -> list[TopicProfile]:
    """Prefer topics with an existing unseen pool when history is unavailable."""
    available = []
    for profile in profiles:
        questions = (
            db.query(Question)
            .filter(Question.section == profile.section)
            .all()
        )
        if any(
            question.id not in excluded_ids
            and question.question_text not in excluded_texts
            and _template_matches(
                question, (profile.section, profile.topic, profile.subtopic)
            )
            for question in questions
        ):
            available.append(profile)
    return available


def _save_generated_question(
    db: Session,
    generated: GeneratedQuestion,
    source: str,
) -> Question:
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
        source=source,
    )
    db.add(question)
    db.flush()
    return question


def _find_unseen_question(
    db: Session,
    profile: TopicProfile,
    difficulty: str,
    excluded_ids: set[int],
    excluded_texts: set[str],
) -> Question | None:
    questions = (
        db.query(Question)
        .filter(Question.section == profile.section, Question.difficulty == difficulty)
        .order_by(Question.id)
        .all()
    )
    return next(
        (
            question
            for question in questions
            if question.id not in excluded_ids
            and question.question_text not in excluded_texts
            and _template_matches(question, (profile.section, profile.topic, profile.subtopic))
        ),
        None,
    )


def create_adaptive_session(
    db: Session,
    request: AdaptivePracticeStartRequest,
    config: AdaptiveSelectionConfig = ADAPTIVE_CONFIG,
    ai_generator: Callable[[QuestionGenerationRequest], AIQuestionResponse] | None = None,
):
    """Create a normal persisted session populated by adaptive selection."""
    profiles = adaptive_topic_profiles(db, request.section, config)
    plan = _topic_plan(profiles, request.question_count, config)
    if not plan:
        raise HTTPException(status_code=400, detail="No adaptive question topics exist for this section")

    session = PracticeSession(
        section=request.section,
        difficulty="Adaptive",
        total_questions=request.question_count,
        started_at=utc_now(),
        time_limit_seconds=request.time_limit_seconds,
        status="active",
    )
    db.add(session)
    db.flush()

    excluded_ids = _previously_attempted_ids(db)
    excluded_texts = _previously_attempted_question_texts(db)
    if not any(profile.attempted for profile in profiles):
        available_profiles = _profiles_with_unseen_questions(
            db, profiles, excluded_ids, excluded_texts
        )
        if available_profiles:
            plan = _topic_plan(available_profiles, request.question_count, config)
    selected_ids: set[int] = set()
    selected_texts: set[str] = set()
    generator = ai_generator or generate_ai_question
    try:
        for order, profile in enumerate(plan, start=1):
            difficulties = difficulty_options_for_accuracy(profile.accuracy, config)
            difficulty = difficulties[(order - 1) % len(difficulties)]
            question = _find_unseen_question(
                db,
                profile,
                difficulty,
                excluded_ids | selected_ids,
                excluded_texts | selected_texts,
            )
            if question is None:
                generation_request = QuestionGenerationRequest(
                    section=profile.section,
                    topic=profile.topic,
                    subtopic=profile.subtopic,
                    difficulty=difficulty,
                    question_type="MCQ",
                )
                generated = None
                for _ in range(MAX_ADAPTIVE_GENERATION_ATTEMPTS):
                    candidate = generator(generation_request)
                    if candidate.question.question_text not in (
                        excluded_texts | selected_texts
                    ):
                        generated = candidate
                        break
                if generated is None:
                    raise RuntimeError("Adaptive generation produced duplicate questions")
                question = _save_generated_question(
                    db,
                    generated.question,
                    f"{generated.generator}-generated original adaptive question",
                )
            selected_ids.add(question.id)
            selected_texts.add(question.question_text)
            db.add(
                SessionQuestion(
                    session_id=session.id,
                    question_id=question.id,
                    question_order=order,
                )
            )
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Adaptive question generation is temporarily unavailable",
        ) from error

    db.commit()
    db.refresh(session)
    return get_session(db, session.id)


def _previously_attempted_question_texts(db: Session) -> set[str]:
    rows = (
        db.query(Question.question_text)
        .join(SessionQuestion, SessionQuestion.question_id == Question.id)
        .join(PracticeSession, SessionQuestion.session_id == PracticeSession.id)
        .filter(PracticeSession.status == "completed")
        .all()
    )
    return {question_text for question_text, in rows}


def _recommendation_reason(profile: TopicProfile) -> str:
    if profile.accuracy is None:
        return "No previous practice history"
    if profile.accuracy < 60:
        return "Low recent accuracy"
    if profile.accuracy < 80:
        return "Developing recent accuracy"
    return "Maintenance practice"


def _section_recommendation(db: Session, section: str, config: AdaptiveSelectionConfig):
    profiles = adaptive_topic_profiles(db, section, config)
    attempted = [profile for profile in profiles if profile.attempted]
    accuracy = (
        round(
            sum(item.correct for item in attempted)
            / sum(item.attempted for item in attempted)
            * 100,
            2,
        )
        if attempted
        else None
    )
    return accuracy, profiles


def recommendation(
    db: Session,
    section: str | None = None,
    config: AdaptiveSelectionConfig = ADAPTIVE_CONFIG,
) -> dict[str, object]:
    """Return transparent next-practice guidance based on recent performance."""
    if section is not None and section not in SECTIONS:
        raise HTTPException(status_code=422, detail="section must be VARC, DILR, or QA")
    section_scores = {item: _section_recommendation(db, item, config) for item in SECTIONS}
    selected_section = section
    if selected_section is None:
        with_history = [
            (score[0], item) for item, score in section_scores.items() if score[0] is not None
        ]
        selected_section = min(with_history)[1] if with_history else "QA"
    profiles = _ordered_profiles(section_scores[selected_section][1])
    selected = profiles[: config.recommendation_topic_count]
    difficulty_source = selected[0].accuracy if selected else None
    return {
        "section": selected_section,
        "recommended_topics": [
            {
                "topic": profile.subtopic,
                "subtopic": profile.subtopic,
                "reason": _recommendation_reason(profile),
                "accuracy": profile.accuracy if profile.accuracy is not None else 0.0,
            }
            for profile in selected
        ],
        "recommended_difficulties": list(
            dict.fromkeys(difficulty_options_for_accuracy(difficulty_source, config))
        ),
    }