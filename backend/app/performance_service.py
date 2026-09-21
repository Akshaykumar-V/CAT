"""Read-only performance calculations from completed practice sessions."""

from collections import defaultdict

from sqlalchemy.orm import Session

from .models import PracticeSession, Question, SessionQuestion


SECTIONS = ["VARC", "DILR", "QA"]
DIFFICULTIES = ["Easy", "Medium", "Hard"]
SLOW_ANSWER_SECONDS = 120


def completed_question_records(db: Session) -> list[tuple[SessionQuestion, Question]]:
    """Return question records belonging only to completed practice sessions."""
    return (
        db.query(SessionQuestion, Question)
        .join(Question, SessionQuestion.question_id == Question.id)
        .join(PracticeSession, SessionQuestion.session_id == PracticeSession.id)
        .filter(PracticeSession.status == "completed")
        .all()
    )


def _metrics(records: list[tuple[SessionQuestion, Question]]) -> dict[str, int | float]:
    """Calculate shared accuracy and answer-time fields for a group of questions."""
    total = len(records)
    attempted_records = [record for record in records if record[0].selected_answer is not None]
    attempted = len(attempted_records)
    correct = sum(session_question.is_correct is True for session_question, _ in attempted_records)
    incorrect = attempted - correct
    unanswered = total - attempted
    total_answer_time = sum(
        session_question.time_spent_seconds or 0
        for session_question, _ in attempted_records
    )
    return {
        "total_questions": total,
        "attempted": attempted,
        "correct": correct,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "accuracy": round((correct / attempted) * 100, 2) if attempted else 0.0,
        "average_time_seconds": round(total_answer_time / attempted, 2)
        if attempted
        else 0.0,
    }


def overall_performance(db: Session) -> dict[str, object]:
    """Calculate app-wide results across completed sessions only."""
    records = completed_question_records(db)
    metrics = _metrics(records)
    sessions = db.query(PracticeSession).filter(PracticeSession.status == "completed").count()
    by_section: dict[str, int] = {}
    for section in SECTIONS:
        section_records = [record for record in records if record[1].section == section]
        by_section[section] = int(_metrics(section_records)["attempted"])
    return {
        **metrics,
        "total_practice_sessions": sessions,
        "questions_solved_by_section": by_section,
    }


def section_performance(db: Session) -> list[dict[str, object]]:
    """Calculate accuracy and average answer time for every CAT section."""
    records = completed_question_records(db)
    results = []
    for section in SECTIONS:
        metrics = _metrics([record for record in records if record[1].section == section])
        results.append({"section": section, **metrics})
    return results


def _category(accuracy: float) -> str:
    if accuracy >= 80:
        return "Strong"
    if accuracy >= 60:
        return "Developing"
    return "Needs Practice"


def topic_performance(db: Session) -> list[dict[str, object]]:
    """Calculate topic metrics and a transparent performance category."""
    grouped: dict[str, list[tuple[SessionQuestion, Question]]] = defaultdict(list)
    for record in completed_question_records(db):
        grouped[record[1].topic].append(record)

    results = []
    for topic in sorted(grouped):
        metrics = _metrics(grouped[topic])
        results.append({"topic": topic, **metrics, "category": _category(float(metrics["accuracy"]))})
    return results


def difficulty_performance(db: Session) -> list[dict[str, object]]:
    """Calculate accuracy and average answer time for every difficulty level."""
    records = completed_question_records(db)
    results = []
    for difficulty in DIFFICULTIES:
        metrics = _metrics([record for record in records if record[1].difficulty == difficulty])
        results.append({"difficulty": difficulty, **metrics})
    return results


def recurring_mistakes(db: Session) -> list[dict[str, object]]:
    """Surface observable issues: incorrect, unanswered, or slow answers by topic."""
    grouped: dict[str, list[tuple[SessionQuestion, Question]]] = defaultdict(list)
    for record in completed_question_records(db):
        grouped[record[1].topic].append(record)

    findings = []
    for topic in sorted(grouped):
        records = grouped[topic]
        metrics = _metrics(records)
        slow_answers = sum(
            session_question.selected_answer is not None
            and (session_question.time_spent_seconds or 0) >= SLOW_ANSWER_SECONDS
            for session_question, _ in records
        )
        signals = []
        if metrics["incorrect"]:
            signals.append("Incorrect answers recorded")
        if metrics["unanswered"]:
            signals.append("Unanswered questions recorded")
        if slow_answers:
            signals.append(f"Answers taking at least {SLOW_ANSWER_SECONDS} seconds")
        if signals:
            findings.append(
                {
                    "topic": topic,
                    "incorrect_answers": metrics["incorrect"],
                    "unanswered_questions": metrics["unanswered"],
                    "slow_answers": slow_answers,
                    "signals": signals,
                }
            )
    return findings


def weak_topics(db: Session) -> dict[str, list[dict[str, object]]]:
    """Group topics by the documented accuracy thresholds."""
    result: dict[str, list[dict[str, object]]] = {
        "strong_topics": [],
        "developing_topics": [],
        "needs_practice": [],
    }
    for topic in topic_performance(db):
        if topic["category"] == "Strong":
            result["strong_topics"].append(topic)
        elif topic["category"] == "Developing":
            result["developing_topics"].append(topic)
        else:
            result["needs_practice"].append(topic)
    return result


def performance_dashboard(db: Session) -> dict[str, object]:
    """Return the key performance summaries for one dashboard API response."""
    categories = weak_topics(db)
    return {
        "overall": overall_performance(db),
        "sections": section_performance(db),
        "strong_topics": categories["strong_topics"],
        "developing_topics": categories["developing_topics"],
        "needs_practice": categories["needs_practice"],
        "difficulty": difficulty_performance(db),
        "recurring_mistakes": recurring_mistakes(db),
    }
