# CAT Prep AI

CAT Prep AI is a single-user MVP for practising VARC, DILR, and QA. It includes original question generation, adaptive and timed practice, full mocks, performance tracking, and a React frontend.

The default metadata is synthetic and is not a verified CAT previous-year dataset. Question generation uses templates unless an external LLM provider is configured. Docker Compose packages the frontend and API together, persists SQLite data, and requires a shared access code. This is a single-user deployment; it does not provide separate student accounts.

## Deploy: Render API and Vercel frontend

1. Push this repository to GitHub. In Render, create a Blueprint from the root `render.yaml`. This uses Render's free web-service plan. During setup, provide a long random `APP_ACCESS_TOKEN`. For `CORS_ORIGINS`, use the final Vercel origin, such as `https://your-project.vercel.app` (no trailing slash).
2. Wait for Render `/health` to return `{"status":"healthy"}`. Copy its HTTPS service URL, such as `https://cat-prep-ai-api.onrender.com`.
3. In Vercel, import the same repository and set **Root Directory** to `frontend`. Set the `VITE_API_URL` environment variable to the Render HTTPS URL. Deploy the project.
4. If Vercel assigns a different domain from the one entered on Render, update Render's `CORS_ORIGINS` to the exact Vercel origin and redeploy the API. Open the Vercel site and enter the Render access code.

Set `VITE_API_URL` for Vercel's Production and Preview environments separately if both are used. Add each allowed preview origin to Render's comma-separated `CORS_ORIGINS`. The access code protects a **single shared account**; do not share it with multiple students expecting separate progress. External LLM generation is optional and requires Render `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL` environment variables.

This free Render deployment is a **temporary demo**. Its SQLite database and imported metadata are stored on an ephemeral filesystem and may disappear after a restart or redeploy. Render may also spin down the service after inactivity, causing a slow first request. Use a persistent disk or external database before relying on saved progress.

## Alternative: deploy both services in one Docker container

1. Install Docker Engine and Docker Compose on the host.
2. Copy `.env.example` to `.env` and set `APP_ACCESS_TOKEN` to a long random secret. Set the optional `LLM_*` variables only if you want provider-backed generation.
3. Run `docker compose up --build -d` from the repository root.
4. Open `http://HOST:8000/app` and enter the access code. The API health endpoint is `http://HOST:8000/health`.

The `cat-prep-data` Docker volume stores the SQLite database across container restarts and rebuilds. Back it up before moving hosts. Put an HTTPS reverse proxy in front of port 8000 before exposing the app on the public internet. Keep the access code private; everyone using it shares the same progress. For local development, the API remains open when `APP_ACCESS_TOKEN` is unset.

Before claiming CAT pattern accuracy, import a verified metadata-only CSV using the documented schema in `data/README.md`. The bundled CSV is synthetic. In the Docker Compose deployment, imported metadata is saved to the persistent volume and loaded again on restart. In the free Render demo, it can disappear on restart.

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
