"""FastAPI application entry point."""

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from . import models
from .analysis import (
    analysis_overview,
    difficulty_distribution,
    load_pyq_data,
    question_type_distribution,
    questions_by_section,
    questions_by_topic,
    section_difficulty_distribution,
    topic_frequency_by_year,
    topic_trends,
)
from .database import Base, engine, get_db
from .practice_service import create_session, finish_session, get_session, submit_answer
from .question_generator import generate_question
from .schemas import (
    GeneratedQuestion,
    GeneratedQuestionBatch,
    QuestionGenerationBatchRequest,
    QuestionGenerationRequest,
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeSessionResponse,
    PracticeStartRequest,
    PracticeSummary,
)


# Create the initial tables when the application starts.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CAT Prep AI API", version="0.1.0")

# The sample file contains only synthetic metadata records for development.
pyq_data = load_pyq_data()


@app.get("/")
def read_root() -> dict[str, str]:
    """Return a small confirmation that the API is available."""
    return {"message": "CAT Prep AI API is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return the service health status."""
    return {"status": "healthy"}


@app.get("/analysis/overview")
def get_analysis_overview() -> dict[str, object]:
    """Return a high-level PYQ metadata summary."""
    return analysis_overview(pyq_data)


@app.get("/analysis/sections")
def get_section_analysis() -> dict[str, object]:
    """Return question counts and difficulty counts for each section."""
    return {
        "questions_by_section": questions_by_section(pyq_data),
        "section_difficulty_distribution": section_difficulty_distribution(pyq_data),
    }


@app.get("/analysis/topics")
def get_topic_analysis() -> dict[str, object]:
    """Return topic counts and their frequency in each year."""
    return {
        "questions_by_topic": questions_by_topic(pyq_data),
        "topic_frequency_by_year": topic_frequency_by_year(pyq_data),
    }


@app.get("/analysis/difficulty")
def get_difficulty_analysis() -> dict[str, object]:
    """Return overall and section-level difficulty distributions."""
    return {
        "difficulty_distribution": difficulty_distribution(pyq_data),
        "section_difficulty_distribution": section_difficulty_distribution(pyq_data),
        "question_type_distribution": question_type_distribution(pyq_data),
    }


@app.get("/analysis/trends")
def get_topic_trends() -> dict[str, object]:
    """Return topic counts by year for trend visualisations."""
    return {"topic_trends": topic_trends(pyq_data)}


@app.post("/questions/generate", response_model=GeneratedQuestion)
def generate_single_question(request: QuestionGenerationRequest) -> GeneratedQuestion:
    """Generate one original CAT-style question from a supported template."""
    return generate_question(request)


@app.post("/questions/generate-batch", response_model=GeneratedQuestionBatch)
def generate_question_batch(
    request: QuestionGenerationBatchRequest,
) -> GeneratedQuestionBatch:
    """Generate a requested number of original CAT-style questions."""
    questions = [generate_question(request) for _ in range(request.count)]
    return GeneratedQuestionBatch(questions=questions)


@app.post("/practice/start", response_model=PracticeSessionResponse)
def start_practice_session(
    request: PracticeStartRequest, db: Session = Depends(get_db)
) -> PracticeSessionResponse:
    """Start a timed session populated with original generated questions."""
    return create_session(db, request)


@app.get("/practice/{session_id}", response_model=PracticeSessionResponse)
def get_practice_session(
    session_id: int, db: Session = Depends(get_db)
) -> PracticeSessionResponse:
    """Get current session state and its question order."""
    return get_session(db, session_id)


@app.post("/practice/{session_id}/answer", response_model=PracticeAnswerResponse)
def answer_practice_question(
    session_id: int,
    request: PracticeAnswerRequest,
    db: Session = Depends(get_db),
) -> PracticeAnswerResponse:
    """Submit one option-label answer for an active session question."""
    return submit_answer(db, session_id, request)


@app.post("/practice/{session_id}/finish", response_model=PracticeSummary)
def finish_practice_session(
    session_id: int, db: Session = Depends(get_db)
) -> PracticeSummary:
    """End a session and return its score summary."""
    return finish_session(db, session_id)
