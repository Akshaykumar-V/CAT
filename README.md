# CAT Prep AI

CAT Prep AI is a one-day MVP foundation for helping CAT aspirants practise VARC, DILR, and QA. Future work will use CAT previous-year-question (PYQ) patterns to support original CAT-style practice, timed sessions, and performance tracking.

This repository currently includes a small FastAPI backend, a SQLite question model, Pydantic validation schemas, a synthetic PYQ metadata CSV, Pandas-based pattern analysis, an original template-based question generator, and timed practice-session APIs. It does not yet include a frontend, authentication, external AI generation, performance tracking, or deployment.

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
- `POST /practice/start` starts a timed practice session with generated questions.
- `GET /practice/{session_id}` returns session state and question progress.
- `POST /practice/{session_id}/answer` records one option-label answer.
- `POST /practice/{session_id}/finish` completes a session and returns its score summary.

The current generator uses templates and generated values only; it does not reproduce or paraphrase CAT questions. It has been kept behind a small service interface so an LLM provider can replace it later.

FastAPI's interactive docs are available at `http://127.0.0.1:8000/docs`.

## Run tests

From the `backend` directory:

```powershell
pytest -q
```
