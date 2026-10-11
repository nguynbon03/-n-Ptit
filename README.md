# SQLArena

SQLArena is a FastAPI workspace for generating, reviewing, and verifying SQL practice questions. MongoDB stores users, questions, documents, jobs, settings, and audit records; a sandboxed in-memory SQLite runner executes answer checks.

## Current product

- Responsive frontend at `/`.
- API health and Swagger UI at `/health` and `/docs`.
- Generation by difficulty, optional Excel target, and background task polling.
- Question bank filtering by difficulty/status, detail view, and review status updates.
- Aggregate stats.
- SQL verification with DDL, seed data, answer query, row count, output, and timeout/error reporting.
- Anthropic-compatible HTTP provider by default; Gemini and NVIDIA remain supported when configured.

This checkout ships MongoDB-backed registration/login/profile auth, learner/admin role checks, safe learner question projections, admin user management, bounded document import, Mongo-authoritative generation jobs, admin LLM settings with a redacted provider test, and audit records for admin mutations. Refresh-token rotation, PostgreSQL persistence, learner submissions, weekly sets, and durable worker infrastructure remain outside this prototype slice.

## Persistence and production boundary

MongoDB is the authoritative store. The in-memory fallback exists only for local development and tests:

- `ENV=local` with no `MONGO_URI`: in-memory store, `/health` reports `persistence: memory`.
- `MONGO_URI` set but unreachable: no silent fallback. `/health` reports `persistence: unavailable` and repository reads/writes fail.
- `ENV=production` or any `VERCEL` value: a missing or unreachable `MONGO_URI` fails startup and `/health` returns `503`.

`/health` never reports `persistence: mongo` unless a Mongo ping succeeded.

Generation runs on FastAPI `BackgroundTasks` inside the API process. That is not a durable queue: an in-flight job is lost on restart and nothing retries it. Mongo job records are the source of truth for status, so `GET /admin/generation-jobs/{id}` still answers after a restart. In production, `POST /admin/generation-jobs` returns `503` unless `ALLOW_BACKGROUND_JOBS=1` explicitly accepts non-durable execution.

The legacy SQLite `QuestionBank` still backs the generation validators and the archive fallback. Review, listing, and learner delivery read the Mongo record written after each run.

## Local setup

Requirements: Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set JWT_SECRET_KEY. Leave MONGO_URI empty for the in-memory dev store.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/`. API documentation is at `http://localhost:8000/docs`.

Check persistence and create the first admin:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/health   # same route through the /api prefix
python scripts/create_admin.py --email admin@example.com
```

`scripts/create_admin.py` writes to whatever store the current environment selects, so set `MONGO_URI` before creating an admin you expect to persist.

## Environment

`.env.example` is the complete template. Keep `.env` private and never commit credentials.

```env
ENV=local
MONGO_URI=
MONGO_DB_NAME=sqlarena
JWT_SECRET_KEY=
JWT_EXPIRE_HOURS=12
MAX_UPLOAD_BYTES=5242880
ALLOW_BACKGROUND_JOBS=0
```

`JWT_SECRET_KEY` is required for every authenticated route. Provider settings:

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

Generation requires a configured provider credential, from either the environment or `PUT /admin/settings/llm`. Health and auth do not call an LLM. Question browsing, stats, generation, document import, and SQL verification require the appropriate authenticated role.

## API examples

Every route is reachable both bare and under one `/api` prefix. Authenticate first:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"your-password"}' | python -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')
```

Start generation and poll the job:

```bash
curl -X POST http://localhost:8000/admin/generation-jobs \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"specs":["easy","medium"],"questions_per_spec":1}'

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/generation-jobs/JOB_ID
```

List and filter questions. Learners only ever receive approved questions without answer, seed, or expected output fields:

```bash
curl -H "Authorization: Bearer $TOKEN" 'http://localhost:8000/questions?difficulty=medium&status=pending_review'
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/stats
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/audit-logs
```

Configure and test the provider. The stored token is never returned:

```bash
curl -X PUT http://localhost:8000/admin/settings/llm \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"provider":"anthropic","model":"claude-sonnet-4-6","api_token":"YOUR_TOKEN"}'

curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/llm/test
```

Import a document. Supported suffixes are `.csv .xlsx .json .md .txt .pdf`, uploads are bounded by `MAX_UPLOAD_BYTES`, and a duplicate checksum returns `409`:

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -F 'file=@questions.csv' http://localhost:8000/admin/documents
```

Verify SQL safely in an in-memory SQLite database:

```bash
curl -X POST http://localhost:8000/verify-sql \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"ddl_sql":"CREATE TABLE users (id INTEGER, name TEXT);","seed_sql":"INSERT INTO users VALUES (1, '\''Ada'\'');","answer_sql":"SELECT * FROM users;"}'
```

## Docker

```bash
docker compose up --build
```

Compose reads provider values from the shell or `.env`; it does not contain credentials. `MONGO_URI` and `JWT_SECRET_KEY` are mandatory because compose runs with `ENV=production`, so compose fails fast rather than starting without persistence. Local SQLite question data persists through `./data`.

## Frontend

Frontend dùng Vite + React + TypeScript trong `frontend/`. Chạy local:

```bash
cd frontend
npm install
npm run dev
```

Vite proxy `/api` tới FastAPI ở `http://127.0.0.1:8000`. Build production bằng `npm run build`.

The access token is kept in module memory only (`frontend/src/api.ts`). It is never written to `localStorage`, `sessionStorage`, or cookies, so reloading the page requires signing in again. There is no refresh endpoint yet; a `401` clears the session and returns to the login screen.

## Vercel

`vercel.json` builds the frontend through the root `package.json`, serves `dist/`, and rewrites `/api/*` to the FastAPI function in `api/index.py`. The `/api` prefix is stripped in exactly one place, `ApiPrefixMiddleware` in `main.py`.

Required server-side environment variables:

- `MONGO_URI` and `MONGO_DB_NAME` — required. Vercel sets `VERCEL`, so a missing or unreachable URI makes `/api/health` return `503` instead of silently using memory.
- `JWT_SECRET_KEY`, optionally `JWT_EXPIRE_HOURS`.
- `AI_PROVIDER`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL` (or the Gemini/NVIDIA equivalents). These can also be set at runtime through `PUT /admin/settings/llm`.
- `ALLOW_BACKGROUND_JOBS=1` only if you accept non-durable in-process generation.
- `MAX_UPLOAD_BYTES` to bound document import.

Deployment smoke sequence:

1. `curl https://<deployment>/api/health` and confirm `persistence: mongo`.
2. Register a learner, then confirm `GET /api/stats` returns `403` for that learner.
3. Create an admin with `scripts/create_admin.py` against the same `MONGO_URI`, then confirm `/api/admin/stats` returns `200`.
4. `PUT /api/admin/settings/llm`, then `POST /api/admin/llm/test`, and confirm the response contains no token.
5. Upload one document twice and confirm the second attempt returns `409`.

### MongoDB Atlas tradeoff

Atlas Network Access `0.0.0.0/0` is an MVP-only shortcut needed because Vercel functions have no stable egress IP. If you use it, pair it with:

- a database user scoped to the single application database, not an Atlas admin,
- a TLS `mongodb+srv://` URI with a long random password,
- a documented rotation plan and prompt revocation of any credential exposed outside the Atlas console.

Prefer an IP access list or private networking as soon as the deployment target supports it. The legacy SQLite question bank is local/ephemeral on serverless deployments; only Mongo data survives.

## Tests and checks

```bash
JWT_SECRET_KEY=test-secret pytest -q
npm --prefix frontend run build
python -m py_compile main.py auth.py mongo_store.py llm_gateway.py pipeline.py
git diff --check
```

Focused suites:

```bash
JWT_SECRET_KEY=test-secret pytest -q tests/test_mongo_store.py tests/test_auth_rbac.py \
  tests/test_document_import.py tests/test_generation_jobs.py \
  tests/test_admin_llm_settings.py tests/test_audit.py \
  tests/test_frontend_boundary.py tests/test_api_prefix.py
```

The app has no committed secrets. Do not paste tokens into source, issues, logs, or deployment files. Rotate any credential exposed outside its provider console.
