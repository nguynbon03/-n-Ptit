# SQLArena

SQLArena is a local-first FastAPI workspace for generating, reviewing, and verifying SQL practice questions. It uses SQLite for the question bank and a sandboxed SQLite runner for answer checks.

## Current product

- Responsive frontend at `/`.
- API health and Swagger UI at `/health` and `/docs`.
- Generation by difficulty, optional Excel target, and background task polling.
- Question bank filtering by difficulty/status, detail view, and review status updates.
- Aggregate stats.
- SQL verification with DDL, seed data, answer query, row count, output, and timeout/error reporting.
- Anthropic-compatible HTTP provider by default; Gemini and NVIDIA remain supported when configured.

The larger design package describes authentication, PostgreSQL, learner submissions, weekly sets, admin RBAC, and worker infrastructure. Those contracts are not implemented in this checkout and are not claimed here.

## Local setup

Requirements: Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/`. API documentation is at `http://localhost:8000/docs`.

## Environment

`.env.example` is the complete template. Keep `.env` private and never commit credentials.

```env
AI_PROVIDER=anthropic
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1/messages
ANTHROPIC_AUTH_TOKEN=
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_DEFAULT_OPUS_MODEL=
```

`ANTHROPIC_MODEL` wins. `ANTHROPIC_DEFAULT_OPUS_MODEL` is only a compatibility fallback when the primary model is empty. The gateway sends the prompt over HTTP with `x-api-key`, Anthropic API version, and JSON content headers. No token is bundled in source, frontend assets, Docker config, or Vercel config.

Optional providers:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

AI_PROVIDER=nvidia
NVIDIA_API_KEY=
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1/chat/completions
NVIDIA_MODEL=google/gemma-4-31b-it
```

Generation requires a configured provider credential. Health, question browsing, stats, and SQL verification do not call an LLM.

## API examples

Start generation:

```bash
curl -X POST http://localhost:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"specs":["easy","medium"],"questions_per_spec":1}'
```

For more than three questions, poll the returned task ID:

```bash
curl http://localhost:8000/tasks/TASK_ID
```

List and filter questions:

```bash
curl 'http://localhost:8000/questions?difficulty=medium&status=pending_review'
curl http://localhost:8000/stats
```

Verify SQL safely in an in-memory SQLite database:

```bash
curl -X POST http://localhost:8000/verify-sql \
  -H 'Content-Type: application/json' \
  -d '{"ddl_sql":"CREATE TABLE users (id INTEGER, name TEXT);","seed_sql":"INSERT INTO users VALUES (1, '\''Ada'\'');","answer_sql":"SELECT * FROM users;"}'
```

## Docker

```bash
docker compose up --build
```

Compose reads provider values from the shell or `.env`; it does not contain credentials. Local question data persists through `./data`.

## Frontend

Frontend dùng Vite + React + TypeScript trong `frontend/`. Chạy local:

```bash
cd frontend
npm install
npm run dev
```

Vite proxy `/api` tới FastAPI ở `http://127.0.0.1:8000`. Build production bằng `npm run build`.

## Vercel

`vercel.json` builds `frontend/` with Vite, serves its output, and rewrites `/api/*` to the FastAPI function in `api/index.py`. Configure these environment variables in Vercel before using generation:

- `AI_PROVIDER`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_MODEL`
- `ANTHROPIC_DEFAULT_OPUS_MODEL`

Gemini/NVIDIA variables are only needed when selecting those providers. SQLite storage is local/ephemeral on serverless deployments; use local Docker or add a persistent database before treating Vercel as production storage.

## Tests and checks

```bash
pytest -q
git diff --check
```

The app has no committed secrets. Do not paste tokens into source, issues, logs, or deployment files. Rotate any credential exposed outside its provider console.
