"""Pydantic schemas used to validate question data."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


VALID_SECTIONS = {"VARC", "DILR", "QA"}
VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}
SUPPORTED_GENERATION_TOPICS = {
    ("QA", "Arithmetic", "Percentages"),
    ("QA", "Arithmetic", "Profit & Loss"),
    ("QA", "Arithmetic", "Ratio"),
    ("QA", "Arithmetic", "Averages"),
    ("QA", "Arithmetic", "Time & Work"),
    ("QA", "Arithmetic", "Time, Speed & Distance"),
    ("QA", "Algebra", "Algebra"),
    ("QA", "Number System", "Number System"),
    ("VARC", "Reading Comprehension", "Reading Comprehension"),
    ("VARC", "Verbal Ability", "Para Summary"),
    ("VARC", "Verbal Ability", "Odd Sentence Out"),
    ("VARC", "Verbal Ability", "Para Jumbles"),
    ("DILR", "Data Interpretation", "Tables"),
    ("DILR", "Logical Reasoning", "Arrangements"),
    ("DILR", "Logical Reasoning", "Distribution"),
    ("DILR", "Logical Reasoning", "Selection"),
    ("DILR", "Logical Reasoning", "Games/Tournaments"),
    ("DILR", "Data Interpretation", "Data Comparison"),
}


class QuestionBase(BaseModel):
    """Fields shared by question input and output schemas."""

    year: int | None = Field(default=None, ge=2000)
    slot: str | None = None
    section: str
    topic: str
    subtopic: str | None = None
    difficulty: str
    question_type: str
    question_text: str
    option_a: str | None = None
    option_b: str | None = None
    option_c: str | None = None
    option_d: str | None = None
    correct_answer: str
    explanation: str | None = None
    source: str


class QuestionCreate(QuestionBase):
    """Schema for adding a question."""


class QuestionResponse(QuestionBase):
    """Schema returned for a saved question."""

    id: int

    model_config = ConfigDict(from_attributes=True)


class QuestionGenerationRequest(BaseModel):
    """Validated input for the template question generator."""

    section: str
    topic: str
    subtopic: str
    difficulty: str
    question_type: str

    @field_validator("section")
    @classmethod
    def validate_section(cls, value: str) -> str:
        if value not in VALID_SECTIONS:
            raise ValueError("section must be VARC, DILR, or QA")
        return value

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        if value not in VALID_DIFFICULTIES:
            raise ValueError("difficulty must be Easy, Medium, or Hard")
        return value

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, value: str) -> str:
        if value != "MCQ":
            raise ValueError("question_type must be MCQ for the template generator")
        return value

    @model_validator(mode="after")
    def validate_supported_template(self) -> "QuestionGenerationRequest":
        if (self.section, self.topic, self.subtopic) not in SUPPORTED_GENERATION_TOPICS:
            raise ValueError("This section, topic, and subtopic combination is not supported")
        return self


class QuestionGenerationBatchRequest(QuestionGenerationRequest):
    """Validated input for a batch of generated questions."""

    count: int = Field(ge=1, le=20)


class GeneratedQuestion(BaseModel):
    """The common output contract for any future question generator provider."""

    question_text: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_answer: str
    explanation: str
    section: str
    topic: str
    subtopic: str
    difficulty: str
    question_type: str


class GeneratedQuestionBatch(BaseModel):
    """Response payload for batch generation."""

    questions: list[GeneratedQuestion]


class QuestionBlueprint(BaseModel):
    """Controlled structure that an original question must target."""

    section: Literal["VARC", "DILR", "QA"]
    topic: str
    subtopic: str
    question_type: Literal["MCQ"]
    difficulty: Literal["Easy", "Medium", "Hard"]
    concepts: list[str] = Field(min_length=1)
    number_of_steps: int = Field(ge=1, le=8)
    reasoning_level: Literal["low", "medium", "high"]
    calculation_load: Literal["low", "medium", "high"]
    information_density: Literal["low", "medium", "high"]
    trap_type: str
    expected_time_seconds: int = Field(ge=15, le=600)
    metadata_signal: dict[str, object] | None = None


class QuestionValidation(BaseModel):
    """Public quality report for a generated question."""

    valid: bool
    checks_passed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ValidatedQuestionResponse(BaseModel):
    """Question, blueprint, and quality report returned by the validated API."""

    question: GeneratedQuestion
    blueprint: QuestionBlueprint
    validation: QuestionValidation


class AIQuestionResponse(BaseModel):
    """Public response for provider-backed generation."""

    question: GeneratedQuestion
    blueprint: QuestionBlueprint
    generator: Literal["llm", "template"]
    validation: QuestionValidation


class PracticeStartRequest(BaseModel):
    """Input for starting a timed practice session."""

    section: str
    difficulty: str
    question_count: int = Field(ge=1, le=20)
    time_limit_seconds: int = Field(ge=60, le=7200)

    @field_validator("section")
    @classmethod
    def validate_practice_section(cls, value: str) -> str:
        if value not in VALID_SECTIONS:
            raise ValueError("section must be VARC, DILR, or QA")
        return value

    @field_validator("difficulty")
    @classmethod
    def validate_practice_difficulty(cls, value: str) -> str:
        if value not in VALID_DIFFICULTIES:
            raise ValueError("difficulty must be Easy, Medium, or Hard")
        return value


class AdaptivePracticeStartRequest(BaseModel):
    """Input for starting a history-aware mixed-difficulty session."""

    section: str
    question_count: int = Field(ge=1, le=20)
    time_limit_seconds: int = Field(ge=60, le=7200)

    @field_validator("section")
    @classmethod
    def validate_adaptive_section(cls, value: str) -> str:
        if value not in VALID_SECTIONS:
            raise ValueError("section must be VARC, DILR, or QA")
        return value


class PracticeAnswerRequest(BaseModel):
    """Input for recording one answer in a session."""

    question_id: int
    selected_answer: str
    time_spent_seconds: int = Field(ge=0)

    @field_validator("selected_answer")
    @classmethod
    def validate_selected_answer(cls, value: str) -> str:
        answer = value.upper()
        if answer not in {"A", "B", "C", "D"}:
            raise ValueError("selected_answer must be A, B, C, or D")
        return answer


class PracticeQuestion(BaseModel):
    """A question as presented inside a practice session."""

    question_id: int
    question_order: int
    section: str
    topic: str
    subtopic: str | None = None
    difficulty: str
    source: str
    question_text: str
    options: dict[str, str]
    answered: bool
    selected_answer: str | None = None
    is_correct: bool | None = None
    correct_answer: str | None = None
    explanation: str | None = None


class PracticeSessionResponse(BaseModel):
    """Session details with answer keys hidden for active sessions."""

    id: int
    section: str
    difficulty: str
    total_questions: int
    started_at: datetime
    finished_at: datetime | None
    time_limit_seconds: int
    status: str
    elapsed_seconds: int
    questions: list[PracticeQuestion]


class PracticeAnswerResponse(BaseModel):
    """Confirmation returned after saving an answer."""

    question_id: int
    selected_answer: str
    is_correct: bool
    answered_at: datetime


class ExplanationRequest(BaseModel):
    """Optional student answer supplied when requesting an explanation."""

    selected_answer: str | None = None

    @field_validator("selected_answer")
    @classmethod
    def validate_explanation_answer(cls, value: str | None) -> str | None:
        if value is None:
            return value
        answer = value.upper()
        if answer not in {"A", "B", "C", "D"}:
            raise ValueError("selected_answer must be A, B, C, or D")
        return answer


class ExplanationResponse(BaseModel):
    """Verified educational explanation for an answered question."""

    question_id: int
    correct_answer: str
    short_answer: str
    concept: str
    approach: str
    steps: list[str] = Field(min_length=1)
    shortcut: str
    common_mistake: str
    difficulty_note: str
    selected_answer: str | None = None
    result: Literal["correct", "incorrect"] | None = None


class ExplanationDraft(BaseModel):
    """Provider-generated explanation fields before server-side verification."""

    short_answer: str
    concept: str
    approach: str
    steps: list[str] = Field(min_length=1)
    shortcut: str
    common_mistake: str
    difficulty_note: str


class PracticeSummary(BaseModel):
    """Scored summary returned when a session is finished or expires."""

    session_id: int
    status: str
    total_questions: int
    attempted: int
    correct: int
    incorrect: int
    unanswered: int
    accuracy: float
    total_time_seconds: int
    average_time_per_attempted_question_seconds: float


MOCK_STATES = {"NOT_STARTED", "IN_PROGRESS", "SECTION_COMPLETE", "COMPLETED", "ABANDONED"}


class MockConfigurationResponse(BaseModel):
    """Public, configurable mock definition."""

    mock_id: str
    title: str
    total_questions: int
    sections: dict[str, int]
    section_order: list[str]
    section_time_limit: dict[str, int]
    total_time_limit: int
    question_ids: list[int]
    status: str


class MockStartRequest(BaseModel):
    mock_id: str


class MockAnswerRequest(BaseModel):
    """Answer or mark one question while the mock is active."""

    question_id: int
    selected_answer: str | None = None
    marked_for_review: bool = False
    time_spent_seconds: int = Field(default=0, ge=0)

    @field_validator("selected_answer")
    @classmethod
    def validate_mock_answer(cls, value: str | None) -> str | None:
        if value is None:
            return value
        answer = value.upper()
        if answer not in {"A", "B", "C", "D"}:
            raise ValueError("selected_answer must be A, B, C, or D")
        return answer


class MockQuestionResponse(BaseModel):
    """Question presented during an active mock, with answer keys hidden."""

    question_id: int
    question_order: int
    section: str
    topic: str
    subtopic: str | None
    difficulty: str
    question_text: str
    options: dict[str, str]
    answered: bool
    selected_answer: str | None
    marked_for_review: bool


class MockSessionResponse(BaseModel):
    """Current server-authoritative mock state."""

    id: int
    mock_id: str
    title: str
    status: str
    current_section: str | None
    section_order: list[str]
    section_remaining_seconds: int
    total_elapsed_seconds: int
    total_time_limit: int
    questions: list[MockQuestionResponse]


class MockSectionResult(BaseModel):
    section: str
    attempted: int
    correct: int
    incorrect: int
    unanswered: int
    accuracy: float
    time_used_seconds: int


class MockTopicResult(BaseModel):
    topic: str
    attempted: int
    correct: int
    accuracy: float


class MockDifficultyResult(BaseModel):
    difficulty: str
    attempted: int
    correct: int
    accuracy: float


class MockResultResponse(BaseModel):
    mock_session_id: int
    status: str
    attempted: int
    correct: int
    incorrect: int
    unanswered: int
    accuracy: float
    total_time_seconds: int
    sections: list[MockSectionResult]
    topics: list[MockTopicResult]
    difficulties: list[MockDifficultyResult]
    strongest_section: str | None
    weakest_section: str | None
    strongest_topics: list[str]
    topics_needing_practice: list[str]
    time_management_observations: list[str]


class MockReviewQuestionResponse(BaseModel):
    question_id: int
    question_order: int
    section: str
    topic: str
    question_text: str
    options: dict[str, str]
    selected_answer: str | None
    correct_answer: str
    is_correct: bool
    explanation: ExplanationResponse


class MockReviewResponse(BaseModel):
    mock_session_id: int
    questions: list[MockReviewQuestionResponse]
