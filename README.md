# CAT Prep AI

CAT Prep AI is a one-day MVP foundation for helping CAT aspirants practise VARC, DILR, and QA. Future work will use CAT previous-year-question (PYQ) patterns to support original CAT-style practice, timed sessions, and performance tracking.

This repository currently includes a small FastAPI backend, a SQLite question model, Pydantic validation schemas, a synthetic PYQ metadata CSV, Pandas-based pattern analysis, an original template-based question generator, timed practice-session APIs, and completed-session performance analysis. It does not yet include a frontend, authentication, external AI generation, or deployment.

## Current architecture

```text
backend/
  app/
    main.py       FastAPI application and basic routes
    database.py   SQLite and SQLAlchemy configuration
    models.py     Question database model
    schemas.py    Pydantic input/output schemas
    analysis.py   CSV validation and Pandas analysis helpers
    question_generator.py  Original template-based question generator
    practice_service.py    Session timing, answer handling, and scoring
    performance_service.py Completed-session accuracy, speed, and category analysis
    adaptive_service.py    History-aware topic and difficulty selection
                            Adaptive sessions reuse unseen questions and generate only missing slots
    blueprint_service.py   Configurable original-question blueprints
    question_validator.py  Deterministic generated-question quality checks
    validated_question_service.py  Bounded blueprint-generation-validation pipeline
    prompt_builder.py      Blueprint-only originality prompt construction
    llm_provider.py        Environment-configured provider abstraction
    ai_question_service.py LLM-first validated generation with template fallback
  tests/
    test_health.py
    test_analysis.py
data/             Synthetic sample metadata and future PYQ datasets
analysis/         Analysis documentation
frontend/         Reserved for the later frontend
```

## Install dependencies

From the project root, create and activate a virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the API

Run this command from the `backend` directory:

```powershell
uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`.

- `GET /` returns `{"message": "CAT Prep AI API is running"}`.
- `GET /health` returns `{"status": "healthy"}`.
- `GET /analysis/overview` returns a high-level question summary.
- `GET /analysis/sections` returns question and difficulty counts by section.
- `GET /analysis/topics` returns question counts by topic and year.
- `GET /analysis/difficulty` returns difficulty and question-type distributions.
- `GET /analysis/trends` returns topic frequencies across years.
- `POST /questions/generate` returns one original question from a supported template.
- `POST /questions/generate-batch` returns 1–20 original questions from a supported template.
- `POST /questions/blueprint` returns the structural blueprint for a supported question.
- `POST /questions/generate-validated` returns an original question, blueprint, and validation report.
- `POST /questions/generate-ai` uses a configured LLM when available and otherwise falls back to the validated template generator.
- `POST /practice/start` starts a timed practice session with generated questions.
- `GET /practice/{session_id}` returns session state and question progress.
- `POST /practice/{session_id}/answer` records one option-label answer.
- `POST /practice/{session_id}/finish` completes a session and returns its score summary.
- `GET /performance/overview` returns overall metrics from completed sessions.
- `GET /performance/sections`, `/topics`, and `/difficulty` return grouped metrics.
- `GET /performance/weak-topics` groups topics by transparent accuracy categories.
- `GET /performance/dashboard` returns a combined performance summary.
- `POST /practice/adaptive-start` starts a mixed-difficulty session using completed practice history.
- `GET /practice/recommendation` recommends a section, topics, and difficulty mix.

The current generator uses templates and generated values only; it does not reproduce or paraphrase CAT questions. It has been kept behind a small service interface so an LLM provider can replace it later.

Adaptive practice first checks for unseen questions matching the selected topic and difficulty. It invokes the validated AI/template generation pipeline only for missing slots, stores generated questions for later analysis, and labels sources as `llm-generated original adaptive question` or `template-generated original adaptive question`.

## Optional LLM configuration

The AI generation endpoint is provider-agnostic and uses an OpenAI-compatible JSON endpoint when configured. Copy `.env.example` to `.env` and provide values locally; `.env` is ignored by git:

```text
LLM_API_KEY=
LLM_MODEL=
LLM_BASE_URL=
LLM_TIMEOUT_SECONDS=20
```

The LLM receives only the structured blueprint, never raw PYQ text. Its JSON output is parsed into the existing question schema and passed through the existing quality validator. Missing configuration, provider failures, malformed output, or exhausted validation retries automatically use the template generator.

FastAPI's interactive docs are available at `http://127.0.0.1:8000/docs`.

## Run tests

From the `backend` directory:

```powershell
pytest -q
```
