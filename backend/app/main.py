"""FastAPI application entry point."""

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models
from .adaptive_service import create_adaptive_session, recommendation
from .ai_question_service import generate_ai_question
from .blueprint_service import generate_blueprint
from .analysis import (
    analysis_overview,
    analysis_summary,
    difficulty_distribution,
    estimated_time_distribution,
    import_metadata_csv,
    load_pyq_data,
    pattern_tags_frequency,
    question_type_distribution,
    questions_by_section,
    questions_by_topic,
    section_difficulty_distribution,
    subtopic_frequency,
    topic_difficulty_relationship,
    topic_frequency_by_slot,
    topic_frequency_by_year,
    topic_trends,
)
from .database import Base, engine, get_db
from .explanation_service import explain_question
from .mock_service import (
    answer_mock_question,
    finish_mock,
    get_mock_configuration,
    get_mock_session,
    list_mocks,
    mock_result,
    mock_review,
    start_mock,
    submit_mock_section,
)
from .practice_service import create_session, finish_session, get_session, submit_answer
from .performance_service import (
    difficulty_performance,
    overall_performance,
    performance_dashboard,
    section_performance,
    topic_performance,
    weak_topics,
)
from .question_generator import generate_question
from .schemas import (
    GeneratedQuestion,
    GeneratedQuestionBatch,
    QuestionGenerationBatchRequest,
    QuestionGenerationRequest,
    AdaptivePracticeStartRequest,
    AIQuestionResponse,
    ExplanationRequest,
    ExplanationResponse,
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeSessionResponse,
    PracticeStartRequest,
    PracticeSummary,
    QuestionBlueprint,
    ValidatedQuestionResponse,
    MockAnswerRequest,
    MockConfigurationResponse,
    MockResultResponse,
    MockReviewResponse,
    MockSessionResponse,
    MockStartRequest,
)
from .validated_question_service import generate_validated_question_or_http


# Create the initial tables when the application starts.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CAT Prep AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "subtopics": subtopic_frequency(pyq_data),
        "topic_frequency_by_slot": topic_frequency_by_slot(pyq_data),
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


@app.post("/analysis/import-metadata")
async def import_metadata(request: Request) -> dict[str, object]:
    """Import metadata from raw CSV text or a JSON ``csv_text`` payload."""
    global pyq_data
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        csv_text = payload.get("csv_text", "")
        if not csv_text and "rows" in payload:
            import pandas as pd

            csv_text = pd.DataFrame(payload["rows"]).to_csv(index=False)
        source = str(csv_text).encode("utf-8")
    else:
        source = await request.body()
    result = import_metadata_csv(source)
    if result.report["valid_rows"]:
        pyq_data = result.data
    return {"report": result.report, "metadata": result.data.to_dict(orient="records")}


@app.get("/analysis/summary")
def get_analysis_summary() -> dict[str, object]:
    return analysis_summary(pyq_data)


@app.get("/analysis/subtopics")
def get_subtopic_analysis() -> dict[str, object]:
    return {"subtopics": subtopic_frequency(pyq_data)}


@app.get("/analysis/patterns")
def get_pattern_analysis() -> dict[str, object]:
    return {
        "sections": questions_by_section(pyq_data),
        "topics": questions_by_topic(pyq_data),
        "subtopics": subtopic_frequency(pyq_data),
        "difficulty": difficulty_distribution(pyq_data),
        "question_types": question_type_distribution(pyq_data),
        "topic_difficulty": topic_difficulty_relationship(pyq_data),
        "estimated_time": estimated_time_distribution(pyq_data),
        "pattern_tags": pattern_tags_frequency(pyq_data),
        "by_slot": topic_frequency_by_slot(pyq_data),
    }


@app.post("/questions/generate", response_model=GeneratedQuestion)
def generate_single_question(request: QuestionGenerationRequest) -> GeneratedQuestion:
    """Generate one original CAT-style question from a supported template."""
    return generate_validated_question_or_http(request, pyq_data).question


@app.post("/questions/generate-batch", response_model=GeneratedQuestionBatch)
def generate_question_batch(
    request: QuestionGenerationBatchRequest,
) -> GeneratedQuestionBatch:
    """Generate a requested number of original CAT-style questions."""
    questions = [
        generate_validated_question_or_http(request, pyq_data).question
        for _ in range(request.count)
    ]
    return GeneratedQuestionBatch(questions=questions)


@app.post("/questions/blueprint", response_model=QuestionBlueprint)
def create_question_blueprint(request: QuestionGenerationRequest) -> QuestionBlueprint:
    """Return the structural blueprint for a supported original question."""
    return generate_blueprint(request, pyq_data)


@app.post("/questions/generate-validated", response_model=ValidatedQuestionResponse)
def generate_validated_question_endpoint(
    request: QuestionGenerationRequest,
) -> ValidatedQuestionResponse:
    """Generate, validate, and return an original question with its blueprint."""
    return generate_validated_question_or_http(request, pyq_data)


@app.post("/questions/generate-ai", response_model=AIQuestionResponse)
def generate_ai_question_endpoint(
    request: QuestionGenerationRequest,
) -> AIQuestionResponse:
    """Generate an original question with an optional LLM and safe fallback."""
    return generate_ai_question(request, metadata=pyq_data)


@app.get("/questions/{question_id}/explanation", response_model=ExplanationResponse)
def get_question_explanation(
    question_id: int, db: Session = Depends(get_db)
) -> ExplanationResponse:
    """Return an explanation only after the question has been answered."""
    return explain_question(db, question_id)


@app.post("/questions/{question_id}/explanation", response_model=ExplanationResponse)
def post_question_explanation(
    question_id: int,
    request: ExplanationRequest,
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    """Return a student-specific explanation after answer submission."""
    return explain_question(db, question_id, request.selected_answer)


@app.post("/practice/start", response_model=PracticeSessionResponse)
def start_practice_session(
    request: PracticeStartRequest, db: Session = Depends(get_db)
) -> PracticeSessionResponse:
    """Start a timed session populated with original generated questions."""
    return create_session(db, request)


@app.post("/practice/adaptive-start", response_model=PracticeSessionResponse)
def start_adaptive_practice_session(
    request: AdaptivePracticeStartRequest, db: Session = Depends(get_db)
) -> PracticeSessionResponse:
    """Start a mixed-difficulty session based on completed practice history."""
    return create_adaptive_session(db, request)


@app.get("/practice/recommendation")
def get_practice_recommendation(
    section: str | None = None, db: Session = Depends(get_db)
) -> dict[str, object]:
    """Recommend a section, topics, and difficulties for the next practice session."""
    return recommendation(db, section)


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


@app.get("/mocks", response_model=list[MockConfigurationResponse])
def get_available_mocks(db: Session = Depends(get_db)) -> list[MockConfigurationResponse]:
    """List configurable mock definitions."""
    return list_mocks(db)


@app.get("/mocks/config/{mock_id}", response_model=MockConfigurationResponse)
def get_mock_config(mock_id: str, db: Session = Depends(get_db)) -> MockConfigurationResponse:
    """Return one mock configuration without starting a session."""
    config = get_mock_configuration(db, mock_id)
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


@app.post("/mocks/start", response_model=MockSessionResponse)
def start_mock_endpoint(request: MockStartRequest, db: Session = Depends(get_db)) -> MockSessionResponse:
    return start_mock(db, request)


@app.get("/mocks/{mock_session_id}", response_model=MockSessionResponse)
def get_mock_session_endpoint(mock_session_id: int, db: Session = Depends(get_db)) -> MockSessionResponse:
    return get_mock_session(db, mock_session_id)


@app.post("/mocks/{mock_session_id}/answer", response_model=MockSessionResponse)
def answer_mock_endpoint(mock_session_id: int, request: MockAnswerRequest, db: Session = Depends(get_db)) -> MockSessionResponse:
    return answer_mock_question(db, mock_session_id, request)


@app.post("/mocks/{mock_session_id}/submit-section", response_model=MockSessionResponse)
def submit_mock_section_endpoint(mock_session_id: int, db: Session = Depends(get_db)) -> MockSessionResponse:
    return submit_mock_section(db, mock_session_id)


@app.post("/mocks/{mock_session_id}/finish", response_model=MockResultResponse)
def finish_mock_endpoint(mock_session_id: int, db: Session = Depends(get_db)) -> MockResultResponse:
    return finish_mock(db, mock_session_id)


@app.get("/mocks/{mock_session_id}/result", response_model=MockResultResponse)
def get_mock_result_endpoint(mock_session_id: int, db: Session = Depends(get_db)) -> MockResultResponse:
    return mock_result(db, mock_session_id)


@app.get("/mocks/{mock_session_id}/review", response_model=MockReviewResponse)
def get_mock_review_endpoint(mock_session_id: int, db: Session = Depends(get_db)) -> MockReviewResponse:
    return mock_review(db, mock_session_id)


@app.get("/performance/overview")
def get_performance_overview(db: Session = Depends(get_db)) -> dict[str, object]:
    """Return overall metrics based only on completed practice sessions."""
    return overall_performance(db)


@app.get("/performance/sections")
def get_performance_sections(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    """Return section-level metrics from completed practice sessions."""
    return section_performance(db)


@app.get("/performance/topics")
def get_performance_topics(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    """Return topic-level metrics and transparent performance categories."""
    return topic_performance(db)


@app.get("/performance/difficulty")
def get_performance_difficulty(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    """Return difficulty-level metrics from completed practice sessions."""
    return difficulty_performance(db)


@app.get("/performance/weak-topics")
def get_weak_topics(db: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    """Group topics using the documented accuracy thresholds."""
    return weak_topics(db)


@app.get("/performance/dashboard")
def get_performance_dashboard(db: Session = Depends(get_db)) -> dict[str, object]:
    """Return a concise combined performance summary."""
    return performance_dashboard(db)
