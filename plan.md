# SQLArena implementation plan

status: APPROVED

## Existing approved intent

The existing approved plan covers prototype cleanup, Anthropic provider support, current-capability frontend, Vercel demo setup, README updates, and tests. It does not approve implementation of the full SQLArena product contract.

Existing approved scope remains unchanged. The requested full SQLArena target is recorded below as a proposed revision only.

---

# Proposed SQLArena target revision

revision_status: APPROVED
approval_required: satisfied by user approval

## Approved architecture deviation
- Primary persistence: MongoDB (MongoDB Atlas for hosted environments, MongoDB service in local Docker or a configured local/remote URI), replacing PostgreSQL in the source design.
- MongoDB implementation must preserve target invariants: unique indexes, transactions where supported, idempotency records, ownership checks, lease/fencing fields, audit events, immutable import manifests, and explicit rollback/compensating operations.
- MongoDB is not a waiver for SQL sandbox isolation: learner SQL still runs only against a separate controlled sandbox service/database.
- Vercel remains frontend/bounded API only; MongoDB, worker, uploads, and sandbox remain external services.
- `MONGO_URI` and `MONGO_DB_NAME` are server-only environment variables; never expose to React or commit values.

## Goal

Build SQLArena as a usable web application from `/Users/nguynbon03/Downloads/Design`: learners register, practice published SQL questions, run and submit SQL safely, review progress and rankings; admins moderate questions, manage weekly sets, import datasets, monitor generation, and resolve reports. Preserve current generation, validation, and question-bank capabilities only where they fit target contracts. Remove public exposure of unsafe prototype routes.

## Scope

### MVP runnable demo

MVP must run locally with PostgreSQL and a separate worker, without fake screens or placeholder success states.

1. Auth: register, login, refresh, logout, password change, current profile.
2. Learner: current published weekly set, paginated questions, redacted question detail, schema view, bounded SQL run, async submit, submission polling/history, progress, leaderboard, week history, report question.
3. Admin: authenticated admin access, question catalog, draft review, approve/reject, generation job creation/status, weekly-set draft/publish/close, report resolve/dismiss, user lock/unlock.
4. Question lifecycle: imported/manual question, draft, review, published, retired, restored; published questions only appear to learners.
5. PostgreSQL persistence and migrations based on target schema.
6. Durable job records and a local worker using PostgreSQL claim/lease semantics.
7. Anthropic generation adapter behind environment configuration, with mocked provider tests and hard budget/rate/concurrency caps.
8. Dataset upload/import for approved CSV/XLSX sources into a server-controlled dataset catalog; no client-provided DDL/seed execution.
9. React screens matching `/Users/nguynbon03/Downloads/Design/docs/screens.md`, with loading, empty, error, confirmation, and unauthorized states.
10. Local Docker Compose startup and production boundary documentation.

MVP does not claim production-grade multi-tenant isolation, high-scale queue throughput, email delivery, enterprise object storage lifecycle, or managed sandbox isolation until production modules below are complete.

### Production-grade modules

These are required before public production launch, not optional polish:

- PostgreSQL execution sandbox isolated outside API request process, with separate DB role/container or service, CPU/memory/process limits, statement and lock timeouts, result/intermediate-resource controls, and killable execution.
- Durable distributed worker deployment with fencing tokens, retry policy, dead-letter handling, cancellation, metrics, tracing, and alerting.
- Managed object storage for uploads, malware scanning, signed access, retention, deletion, and immutable import manifests.
- Redis or equivalent distributed rate limiting if PostgreSQL rate limits do not meet measured load.
- Password reset email provider, email verification, abuse controls, and delivery monitoring.
- Secret manager, key rotation, centralized redacted logs, audit export, and incident response runbook.
- Load, concurrency, migration rehearsal, disaster recovery, restore, and cross-instance tests.
- Production dataset tenancy/isolation review and formal AI evaluation against held-out fixtures.

## Non-goals

- No fake placeholder API responses, local-only state presented as durable state, or frontend-only authorization.
- No learner access to `reference_sql`, answer SQL, expected output, hidden test cases, internal blueprint, review notes, provider output, or seed/DDL internals.
- No arbitrary client-supplied DDL, seed SQL, database URL, provider URL, model, prompt, or filesystem path.
- No public deployment of current anonymous prototype routes.
- No SQLite as runtime persistence for target features. SQLite may remain only in isolated legacy tests until retired.
- No Vercel-hosted durable worker, durable local filesystem, or production PostgreSQL execution sandbox.
- No advanced dashboard, streak system, retention analytics, scheduler UI, or other screens explicitly excluded by `docs/screens.md` until a separate approved revision.

## Evidence and source contracts

Read and implement against these immutable design inputs:

- `/Users/nguynbon03/Downloads/Design/api/openapi.yaml`
- `/Users/nguynbon03/Downloads/Design/db/postgres_schema.sql`
- `/Users/nguynbon03/Downloads/Design/db/seed_core.sql`
- `/Users/nguynbon03/Downloads/Design/docs/business_rules.md`
- `/Users/nguynbon03/Downloads/Design/docs/implementation_contracts.md`
- `/Users/nguynbon03/Downloads/Design/docs/implementation_scope_and_handoff.md`
- `/Users/nguynbon03/Downloads/Design/docs/screens.md`
- `/Users/nguynbon03/Downloads/Design/docs/test_plan.md`
- `/Users/nguynbon03/Downloads/Design/docs/enterprise_dataset_contract.md`
- `/Users/nguynbon03/Downloads/Design/docs/question_quality_criteria.md`
- `/Users/nguynbon03/Downloads/Design/docs/ai_evaluation_plan.md`
- `/Users/nguynbon03/Downloads/Design/schemas/model_a_output.schema.json`
- `/Users/nguynbon03/Downloads/Design/schemas/model_b_output.schema.json`
- `/Users/nguynbon03/Downloads/Design/schemas/checklist_output.schema.json`

If target design and current prototype conflict, target contract wins for new routes. Legacy capability is retained only behind authenticated/admin-safe adapters and only when response secrecy and lifecycle rules remain correct.

## Architecture

Use one versioned FastAPI application with explicit domain modules, PostgreSQL repositories, and a separate worker process. Keep frontend and API deployable separately. Keep request handlers thin: validate transport input, authorize, call application service, map typed result/error. Repositories own SQL and transaction boundaries; domain services own state transitions; workers own claim/lease/retry.

```text
React/Vite browser
  -> Vercel static frontend or local Vite dev server
  -> FastAPI API service
     -> PostgreSQL: users, sessions, questions, weekly sets, submissions, jobs, audits
     -> object storage: uploaded source files and immutable import manifests
     -> Anthropic API: server-side generation only
  -> worker service
     -> PostgreSQL job claim/lease
     -> isolated SQL execution service for run/grading
```

Default deployment split:

- Vercel: frontend static assets and, only if needed, bounded stateless API proxy/functions.
- Container platform or VM: FastAPI API, worker, and production SQL execution service.
- Managed PostgreSQL: durable application data.
- Object storage: upload files and import artifacts.

Do not make Vercel function memory or `/tmp` the source of truth.

## Stack and runtime contract

- Backend: Python 3.11+; FastAPI; Pydantic v2; async PostgreSQL driver (`asyncpg`) or SQLAlchemy async with one chosen repository style; Alembic migration runner if SQLAlchemy is selected.
- Frontend: React, Vite, TypeScript. Add a router and a small API/query layer; do not add a state library unless implementation proves local hooks insufficient.
- Database: PostgreSQL 15+ locally and production-compatible managed PostgreSQL.
- Worker: Python process using same application services and PostgreSQL leasing; no FastAPI `BackgroundTasks` for durable jobs.
- Package managers: `pip`/`requirements.txt` or locked Python project metadata; `npm` for `frontend/`.
- Backend tests: `pytest`, HTTP client tests, PostgreSQL integration tests.
- Frontend tests: TypeScript build, route/component tests, browser smoke tests once runner is selected.
- Timezone: persist UTC; display Ho Chi Minh timezone where UI requires local time.
- IDs: use target schema ID types and server-generated IDs. Do not expose sequential internal IDs where target uses UUIDs.

## Target file/module map

### Backend files to replace or narrow

- `main.py`: retain only app construction, middleware, router registration, health, startup/shutdown. Remove anonymous generation/status/stat/SQL verification exposure.
- `api/index.py`: retain only a thin Vercel ASGI adapter if Vercel API proxy remains; remove duplicate path-prefix behavior and document one canonical routing rule.
- `pipeline.py`: refactor into durable generation application service; no process-memory task registry.
- `llm_gateway.py`: retain provider abstraction, add Anthropic contract, budget/correlation/error normalization, prompt/model version capture.
- `execution_engine.py`: keep only legacy test adapter until isolated execution service is available; never use it as production security boundary.
- `question_bank.py`: retire runtime SQLite CRUD; migrate compatible validation/serialization helpers into repositories/services.
- `requirements.txt`: add PostgreSQL/migration/security dependencies selected by implementation; do not add duplicate ORM/driver stacks.
- `README.md`: replace prototype-only claims with local/demo/production boundary and exact commands.
- `Dockerfile`: API image only; add separate worker image/command if same image is reused.
- `docker-compose.yml`: PostgreSQL, API, worker, frontend development services; no claim that local SQLite is target persistence.
- `vercel.json`: static frontend and bounded rewrite only; no durable worker or SQLite assumptions.
- `package.json`: root orchestration commands only.
- `.env.example`: names and safe dummy values only.
- `.gitignore`: keep `.env*`, local DB dumps, uploads, build output, test secrets ignored.

### Backend modules to create

- `app/` package as canonical target runtime.
- `app/config.py`: typed environment settings and startup validation.
- `app/main.py`: application factory, middleware, router registration.
- `app/errors.py`: public error envelope and exception mapping.
- `app/db.py`: PostgreSQL pool/session lifecycle and transaction helper.
- `app/security/passwords.py`: Argon2id or bcrypt password hashing and verification.
- `app/security/tokens.py`: short-lived access JWT, refresh-token hashing/rotation/replay detection.
- `app/security/csrf.py`: Origin/Referer enforcement for cookie-authenticated state-changing requests.
- `app/security/rate_limit.py`: authenticated and anonymous route budgets with backend-backed counters.
- `app/security/authorization.py`: role, account status, ownership, and lock checks.
- `app/observability.py`: request ID, structured redacted logging, audit event helper.
- `app/api/dependencies.py`: DB, current user, role, request ID, idempotency dependencies.
- `app/api/auth.py`: auth/profile routes.
- `app/api/learner.py`: weekly/practice/progress/history/report routes.
- `app/api/admin.py`: admin account/question/review/report/job/weekly routes.
- `app/api/schemas/auth.py`, `learner.py`, `admin.py`, `common.py`: transport DTOs matching OpenAPI.
- `app/domain/auth/`, `weekly/`, `questions/`, `submissions/`, `reports/`, `generation/`, `imports/`, `users/`: state machines and application services.
- `app/repositories/`: `users.py`, `sessions.py`, `questions.py`, `weekly_sets.py`, `submissions.py`, `reports.py`, `generation_jobs.py`, `imports.py`, `audit_logs.py`, `settings.py`, `prompts.py`.
- `app/worker/runner.py`: polling loop, shutdown, metrics, claim/lease dispatch.
- `app/worker/handlers.py`: generation, grading, import, weekly close handlers.
- `app/worker/lease.py`: claim, heartbeat, fencing, retry, dead-letter behavior.
- `app/llm/anthropic.py`: Anthropic Messages API adapter; server-side only.
- `app/llm/contracts.py`: Model A, Model B, checklist typed contracts.
- `app/llm/prompts.py`: prompt registry/version resolver; no secrets.
- `app/llm/gates.py`: schema, clarity, novelty, semantic, safety, and evidence gates.
- `app/datasets/catalog.py`: allowlisted dataset/version resolution.
- `app/datasets/import_service.py`: upload validation, parse, normalize, import manifest, rollback.
- `app/sandbox/client.py`: API to isolated SQL execution service; no direct arbitrary SQL in API process.
- `app/sandbox/contracts.py`: run/result/grading DTOs and resource limits.
- `app/migrations/versions/`: ordered SQL/ORM migrations; no runtime schema creation.
- `app/seeds/`: idempotent core/dev seed loaders.

### Frontend files to create or replace

- `frontend/src/app/router.tsx`: protected/public/admin route tree.
- `frontend/src/app/AppShell.tsx`: navigation and global error/session handling.
- `frontend/src/api/client.ts`: typed fetch, in-memory access token, refresh retry, error envelope.
- `frontend/src/api/contracts.ts`: generated or manually synchronized OpenAPI DTO types.
- `frontend/src/auth/AuthProvider.tsx`: memory-only access token and session state.
- `frontend/src/auth/guards.tsx`: auth/admin/locked-user route behavior.
- `frontend/src/components/LoadingState.tsx`, `EmptyState.tsx`, `ErrorState.tsx`, `ConfirmDialog.tsx`, `Pagination.tsx`, `FormField.tsx`.
- `frontend/src/features/auth/`: register, login, forgot/reset password, profile, password change.
- `frontend/src/features/learner/`: weekly list, question detail, SQL editor, run result, submit/result polling, history, progress, leaderboard, weeks, report form.
- `frontend/src/features/admin/`: users, question catalog, draft review, generation jobs, weekly sets, reports, dataset import.
- `frontend/src/features/shared/`: date formatting, error mapping, idempotency key, feature flags.
- `frontend/src/styles/`: tokenized flat-colour visual system; no gradients; accessible focus and mobile input sizing.
- `frontend/src/test/`: route, API contract, auth secrecy, and component tests.
- `frontend/vite.config.ts`: local `/api` proxy only; production API origin from public config, never secret.

### Contract and operational files to create

- `docs/sqlarena/architecture.md`
- `docs/sqlarena/api-contract.md`
- `docs/sqlarena/security-model.md`
- `docs/sqlarena/import-contract.md`
- `docs/sqlarena/worker-operations.md`
- `docs/sqlarena/vercel-boundary.md`
- `docs/sqlarena/mvp-vs-production.md`
- `docs/sqlarena/rollback.md`
- `docs/sqlarena/test-matrix.md`
- `scripts/db-migrate.sh`
- `scripts/db-seed.sh`
- `scripts/run-api.sh`
- `scripts/run-worker.sh`
- `scripts/import-dataset.sh`
- `tests/integration/`
- `tests/security/`
- `tests/contract/`
- `tests/worker/`
- `tests/fixtures/`

## Database and migration plan

### Schema source

Start from `/Users/nguynbon03/Downloads/Design/db/postgres_schema.sql`. Compare every table, enum, foreign key, check constraint, unique index, and index with implementation repositories before adding application-specific columns. Do not silently fork target names. Any necessary deviation becomes a DRAFT revision with reason and compatibility impact.

Target domains:

- users, roles, account status, refresh sessions/tokens, password reset records;
- worlds, dataset catalog, dataset versions, import manifests and source metadata;
- skills, templates, prompts, settings registry;
- questions, question sources, lifecycle/status, published visibility, retirement/restore;
- question drafts, model runs, checklist/evidence, review leases and decisions;
- test cases, expected result references, run evidence;
- weekly sets, weekly items, publish/close/cutoff state, warnings/deficits;
- submissions, submission state transitions, idempotency records, result summaries;
- reports and moderation decisions;
- generation/import/grading jobs, attempts, leases, retries, failures;
- audit logs.

### Migration sequence

1. `0001_extensions_and_enums`: UUID strategy, timestamps, target enums, required extensions only.
2. `0002_identity_and_sessions`: users, roles, refresh sessions, reset records, indexes.
3. `0003_worlds_datasets_imports`: dataset catalog/version, source/import manifests, ownership/status constraints.
4. `0004_question_core`: skills/templates/questions/sources/lifecycle fields and learner-safe projections.
5. `0005_drafts_review_evidence`: drafts, model runs, test cases, locks/leases, approval evidence.
6. `0006_weekly_sets`: weekly lifecycle, items, uniqueness rules, cutoff and close fields.
7. `0007_submissions_and_reports`: submission state machine, idempotency, reports, ownership indexes.
8. `0008_jobs_and_audit`: durable jobs, attempts, leases/fencing, audit logs, settings/prompts.
9. `0009_legacy_import`: one-time controlled import from `data/questions.db` only after field mapping and redaction review; never expose imported legacy rows automatically.
10. `0010_constraints_and_indexes`: only after integration fixtures pass; add validated constraints/indexes with measured query plans.

Each migration must be forward-only, transaction-safe where PostgreSQL permits, reversible through documented rollback or compensating migration, and tested against an empty database plus a representative seeded database. Production migrations run separately from app startup.

### Transaction rules

- Auth refresh rotation, logout, password changes, lock/unlock, and audit event: one transaction.
- Question approval plus selected model run, evidence, test cases, question publication, and audit event: one transaction; reject if evidence is missing or unstable.
- Weekly publish/close and item changes: transaction with row locks and conflict detection.
- Submission creation/idempotency record: transaction; duplicate same payload returns original resource, changed payload returns `409`.
- Worker claim updates lease/fence atomically; handler result commits state and audit together.
- Import creates an immutable manifest and only promotes validated rows in a transaction; failed import leaves prior catalog unchanged.

## API contract

All public errors use:

```text
{ "code": string, "message": string, "details": object }
```

All list endpoints use `page`, `page_size`, `total`, and `items`, with server maximums. All protected mutating endpoints enforce role, account status, CSRF policy, and audit logging. State-changing retriable operations accept `Idempotency-Key` where specified by OpenAPI.

### Auth/profile

- `POST /auth/register`: validate email/password, create active or pending user per design, return safe user/access response; never return password or token secrets in logs.
- `POST /auth/login`: verify password/status, return short-lived access JWT; set rotated HttpOnly Secure SameSite refresh cookie.
- `POST /auth/refresh`: rotate refresh cookie, reject replay, revoke token family on replay.
- `POST /auth/logout`: revoke current refresh session; work without a valid access token when refresh cookie is present.
- `POST /auth/password/forgot`: non-disclosing response for unknown email; create expiring single-use reset record.
- `POST /auth/password/reset`: consume reset record, rotate/revoke sessions.
- `PUT /me/password`: current password plus new password, revoke other sessions per design.
- `GET /me`, `PATCH /me`: safe profile only; lock/role changes take effect on next authorization check.

### Learner

- `GET /weekly/current`: server-resolved current published set summary and cutoff/status.
- `GET /weekly/current/questions`: paginated questions, difficulty/skill/solved filters; learner projection excludes reference material.
- `GET /questions/{questionId}`: published/current-access checks; returns prompt, allowed dataset/schema metadata, public constraints only.
- `GET /questions/{questionId}/run`: run without saving submission, allowlisted dataset only, bounded result contract, no hidden expected output.
- `POST /questions/{questionId}/submit`: SQL plus `Idempotency-Key`; immutable submission input; enqueue grading; duplicate same payload returns same submission.
- `GET /submissions/{submissionId}`: owner/admin authorization; state and safe result summary.
- `GET /me/submissions`: paginated personal history; no hidden tests/reference SQL.
- `POST /questions/{questionId}/reports`: one open report per learner/question; duplicate open report returns `409`.
- `GET /me/progress`: global non-resetting progress and current-week summary.
- `GET /weekly/{setId}/leaderboard`: published/closed visibility and competition ranking with solved count/tie handling.
- `GET /me/weeks`: summary-only week history; closed-week rules apply.

### Admin

Implement all OpenAPI admin groups with role checks, pagination, audit visibility, and confirmation requirements:

- users: list/search/filter, lock/unlock, role/status changes, self-lock/self-demotion prevention;
- worlds/dataset versions and upload/import status;
- skills/templates/settings/prompts with hard caps and activation audit;
- question catalog/source toggle/retire/restore;
- draft list/detail, review lease, selected Model B run, approve/reject reason;
- reports open/resolved/dismissed and question linkage;
- generation job create/list/detail with one difficulty per job, quantity cap, idempotency, budget/rate-limit errors;
- weekly set create, deficits/warnings/supplemental jobs, replacement, publish gate, close, conflict handling.

### Internal worker contract

Job payloads contain IDs and versioned parameters only. Worker resolves all secrets, prompts, datasets, and limits server-side. Job states are `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, `dead_letter`; every transition records attempt, worker fence, timestamps, and redacted failure code.

## Upload/import flow

1. Admin requests an import session with filename, declared type, byte size, checksum, and intended dataset metadata.
2. API authenticates admin, enforces size/type/rate limits, creates pending import manifest, and returns a short-lived upload target. MVP may use multipart upload to API with strict limits; production uses signed object-storage upload.
3. Upload handler stores bytes outside repository/runtime filesystem, checks checksum, rejects path traversal, macro-enabled or unsupported formats, oversized archives, and content-type spoofing.
4. Import job parses CSV/XLSX using an allowlisted parser, normalizes headers/types, rejects formulas/macros and malformed rows, samples schema, and records validation errors without executing cells or SQL.
5. Dataset service creates a new immutable dataset version. It does not replace an active version until validation and admin confirmation pass.
6. Import maps columns to target schema metadata and generates server-owned DDL/seed representation. Client cannot submit executable DDL/seed as authority.
7. Admin reviews row counts, columns, type inference, PII flags, warnings, and checksum; confirms promotion.
8. Worker builds the isolated execution dataset from the approved version, runs schema/fixture checks, and marks version available.
9. Failed import leaves prior version active and exposes safe error codes plus admin-only diagnostics. Delete/retention follows object-storage policy.

## Anthropic environment contract

Server-only environment variables:

- `ANTHROPIC_BASE_URL`: approved API base URL; default official endpoint only when explicitly supported by implementation.
- `ANTHROPIC_AUTH_TOKEN`: secret token; never sent to browser, never returned by config/status endpoints, never logged.
- `ANTHROPIC_MODEL`: default model identifier for generation.
- `ANTHROPIC_DEFAULT_OPUS_MODEL`: compatibility fallback only when `ANTHROPIC_MODEL` is unset and implementation explicitly permits fallback.
- `ANTHROPIC_TIMEOUT_SECONDS`: bounded request timeout.
- `ANTHROPIC_MAX_RETRIES`: hard retry ceiling.
- `ANTHROPIC_MAX_INPUT_TOKENS`, `ANTHROPIC_MAX_OUTPUT_TOKENS`: request caps.
- `LLM_DAILY_BUDGET_USD`, `LLM_JOB_CONCURRENCY`, `LLM_RATE_LIMIT_PER_ADMIN`: server-side guardrails.

Provider configuration must be validated at startup for worker/generation processes, not required for learner-only API startup if generation is disabled. Provider errors map to stable internal codes; raw provider responses and prompts are redacted from public errors and logs. Persist provider name, model ID, prompt version, request ID, token counts, estimated cost, and gate result; never persist token values.

Anthropic adapter requirements:

- Messages API request/response contract isolated in `app/llm/anthropic.py`.
- Structured output validation against target Model A/Model B/checklist schemas.
- Prompt caching only if supported by selected SDK/API contract and measured useful; no cache feature is required for MVP correctness.
- Retry only transient errors with bounded exponential backoff and budget accounting.
- Circuit-open behavior after repeated provider failures.
- Mocked provider tests cover success, malformed JSON, timeout, rate limit, authentication failure, budget exhaustion, and retry exhaustion.

## Local, demo, and production commands

Commands are contractual targets; implementation must make them work and document actual output/ports.

### Local prerequisites

- Docker Desktop.
- Python 3.11+.
- Node.js LTS and npm.
- PostgreSQL supplied by Docker Compose for normal local use.
- Optional local Anthropic credentials in untracked `.env`; tests default to mock provider.

### Local startup

```text
docker compose up --build postgres api worker
npm --prefix frontend install
npm --prefix frontend run dev
```

Expected local services:

- frontend: `http://localhost:5173`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs` for local development only
- PostgreSQL: bound only to localhost if host binding is needed
- worker: no public port

### Database operations

```text
./scripts/db-migrate.sh
./scripts/db-seed.sh
```

Migration command must fail closed when `DATABASE_URL` is missing or points to an unapproved environment. Seeds must be idempotent and never contain real credentials.

### Test commands

```text
pytest -q
pytest -q tests/contract tests/security tests/integration tests/worker
npm --prefix frontend run build
npm --prefix frontend run test
```

Add one documented command for PostgreSQL integration tests, such as a Compose test profile. Do not label SQLite-only tests as target integration proof.

### Production release sequence

1. Build and scan API, worker, and frontend artifacts.
2. Apply migrations using release identity, not app startup.
3. Run smoke checks against staging PostgreSQL and worker.
4. Deploy API and worker with old contract compatibility window.
5. Deploy frontend after API contract is live.
6. Verify health, auth, learner run/submit, admin job, and audit events.
7. Monitor error rate, queue age, provider cost, database saturation, and sandbox failures.
8. Roll back app artifacts first; roll back migrations only through tested compensating migration.

## Vercel role and limitations

Vercel may host the built React/Vite frontend and optionally route `/api` to a bounded stateless FastAPI function. Vercel is not the source of truth for PostgreSQL data, uploads, jobs, worker state, or execution sandboxes.

Required Vercel rules:

- Configure frontend build from `frontend/` through root `package.json` or Vercel project settings; verify no root/`frontend` package mismatch.
- Use one `/api` prefix rule. Do not strip the prefix both in `api/index.py` and application middleware.
- Set only public frontend variables in Vercel browser build. `ANTHROPIC_AUTH_TOKEN`, `DATABASE_URL`, signing keys, storage credentials, and worker credentials stay server-side in the API/worker environment.
- Do not use `/tmp` or process memory for durable tasks, sessions, uploaded files, or questions.
- Do not run generation, grading, import, or weekly close as fire-and-forget request background work.
- Respect function timeout/body limits. Long-running work returns a durable job ID and is handled by external worker.
- Configure CORS to exact frontend origins; never use wildcard origins with credentials.
- If Vercel cannot provide required FastAPI runtime behavior or timeout, deploy API separately and keep Vercel frontend-only.

## Security gates

No public demo passes security gate until all applicable gates pass:

1. Anonymous callers cannot read learner/admin data or invoke generation/status/SQL execution.
2. Every protected route has explicit authentication and role/ownership checks.
3. Locked users cannot log in, refresh, submit, report, or use admin APIs.
4. Refresh tokens are HttpOnly, Secure in production, SameSite policy documented, rotated, hashed at rest, replay-detected, and revoked on logout/password reset.
5. Access JWT remains in frontend memory only; never Web Storage, URL, logs, or error payload.
6. CSRF Origin/Referer checks cover cookie-authenticated state changes.
7. CORS allowlist contains exact configured origins; credentials are not combined with wildcard origins.
8. Public errors use stable codes and contain no stack traces, SQL, provider body, secrets, prompt text, or answer data.
9. Learner DTOs redact `reference_sql`, answer SQL, expected output, hidden tests, schema/seed internals, blueprint, review notes, and provider metadata.
10. SQL run/grading resolves server-owned dataset/version and uses isolated execution. Regex blacklist alone is not accepted.
11. SQL resources have statement timeout, lock timeout, row/result limit, request size limit, concurrency limit, and killable execution.
12. Uploads enforce size/type/checksum/content validation, path safety, malware scanning plan, and object retention.
13. Generation is admin-only, idempotent, rate-limited, concurrency-limited, budget-limited, and durable.
14. Audit logs cover auth/security changes, admin actions, imports, approvals, publish/close, job transitions, and report decisions.
15. Secret scanning and `git diff --check` pass; no real token or credential appears in tracked files, fixtures, logs, screenshots, or seed data.
16. IDOR tests cover every user-owned submission/report/session and every admin resource.

## Frontend routes and behavior

### Public routes

- `/login`
- `/register`
- `/forgot-password`
- `/reset-password`

### Learner protected routes

- `/app`: dashboard/current weekly set summary.
- `/app/weekly/current`: current set, filters, pagination, solved state, deficits/warnings.
- `/app/questions/:questionId`: prompt, public schema, SQL editor, run, submit, result polling, report.
- `/app/submissions`: personal history and safe summaries.
- `/app/progress`: global progress and current week summary.
- `/app/leaderboard`: current or selected published/closed week ranking.
- `/app/weeks`: week history summary.
- `/app/profile`: profile and password change.

### Admin protected routes

- `/admin/users`
- `/admin/questions`
- `/admin/drafts/:draftId`
- `/admin/generation`
- `/admin/weekly-sets`
- `/admin/reports`
- `/admin/imports`

Every route handles loading, empty, error, unauthorized, locked/session-expired, retry, and destructive-action confirmation states. Admin screens show audit actor/time and conflict responses. Date display uses Ho Chi Minh timezone while API stores UTC.

## Phased WBS

Each task has one exclusive write scope. Shared contract files have one owner: `T00` owns `docs/sqlarena/*`, root routers, and this proposed plan after approval; other tasks consume frozen contracts only.

### Wave 0 — contract freeze and safety stop

#### T00: Target contract and execution packet

- Profile: `dev-sa`
- Agent: `dev-orchestration-agent`
- Primary skill: `sd-system-design`
- Files: `docs/sqlarena/architecture.md`, `docs/sqlarena/api-contract.md`, `docs/sqlarena/security-model.md`, `docs/sqlarena/mvp-vs-production.md`, `docs/sqlarena/test-matrix.md`, `plan.md` revision section, `.claude/agent-routing.json`
- Action: reconcile target OpenAPI/schema/business rules into frozen MVP contracts; record explicit deviations from current approved prototype plan.
- Proof: contract review maps every MVP acceptance condition to endpoint, data state, frontend route, and test gate.
- Done: no unresolved endpoint ownership, secret boundary, migration owner, or worker lifecycle decision.
- Dependencies: none.
- Write scope: contract/docs only; no runtime source.

### Wave 1 — platform and database

#### T01: PostgreSQL runtime and migrations

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `sd-data-storage`
- Files: `app/db.py`, `app/config.py`, `app/migrations/versions/0001_*` through `0010_*`, `app/seeds/*`, `scripts/db-migrate.sh`, `scripts/db-seed.sh`, `tests/integration/test_migrations.py`
- Action: implement target schema, migration runner, pool lifecycle, transaction helper, seed strategy, legacy import mapping.
- Proof: empty DB migration, seeded DB migration, rollback/compensating migration check, foreign-key and uniqueness tests.
- Done: no runtime schema creation; repositories can use target tables; SQLite is not used by target paths.
- Dependencies: T00.
- Write scope: DB/config/migrations only.

#### T02: Error, request, audit, and repository foundations

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `superpowers-test-driven-development`
- Files: `app/errors.py`, `app/observability.py`, `app/api/dependencies.py`, `app/repositories/*.py`, `tests/contract/test_error_envelope.py`, `tests/integration/test_repositories.py`
- Action: create typed error envelope, request correlation, audit helper, pagination, repository interfaces, and transaction boundaries.
- Proof: error/status/pagination contract tests and repository integration tests against PostgreSQL.
- Done: route handlers can return stable contract without leaking internal errors.
- Dependencies: T01.
- Write scope: shared backend foundations and repository modules.

#### T03: Authentication, sessions, and authorization

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `superpowers-test-driven-development`
- Files: `app/security/*`, `app/api/auth.py`, `app/domain/auth/*`, `app/repositories/users.py`, `app/repositories/sessions.py`, `tests/security/test_auth.py`, `tests/security/test_rbac.py`, `tests/security/test_csrf_cors.py`
- Action: implement register/login/refresh/logout/reset/profile, password hashing, token rotation/replay detection, lock/status, RBAC, CSRF, CORS, rate limits.
- Proof: anonymous/learner/admin/locked matrix, cookie flags, replay, reset non-disclosure, IDOR, self-lock/self-demotion, rate-limit tests.
- Done: no protected target route is reachable without required authorization; frontend can use memory-only access token.
- Dependencies: T01, T02.
- Write scope: security/auth backend only.

#### T04: API shell and route compatibility

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `sd-api-design`
- Files: `app/main.py`, `main.py`, `api/index.py`, `app/api/schemas/*`, `tests/contract/test_openapi_routes.py`
- Action: register versioned routers, normalize `/api` behavior, map OpenAPI paths/statuses, remove or protect legacy routes.
- Proof: route inventory matches target OpenAPI; legacy unsafe endpoints return authenticated/admin-safe responses or `404`.
- Done: one canonical API prefix and stable public error contract.
- Dependencies: T02, T03.
- Write scope: app construction, API DTOs, route registration.

### Wave 2 — learner domain and sandbox boundary

#### T05: Dataset catalog and import MVP

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `superpowers-test-driven-development`
- Files: `app/datasets/*`, `app/api/admin.py` import slice, `app/repositories/imports.py`, `tests/integration/test_imports.py`, `tests/security/test_uploads.py`, `docs/sqlarena/import-contract.md`
- Action: implement strict upload/import manifest, CSV/XLSX validation, immutable dataset versions, admin promotion, rollback on failed import.
- Proof: valid/invalid file tests, checksum/size/type/path tests, malformed workbook tests, failed promotion leaves active version unchanged.
- Done: no client SQL/DDL is execution authority; imported version is addressable by server ID.
- Dependencies: T01–T04.
- Write scope: dataset/import backend and import docs.

#### T06: Question catalog and weekly lifecycle

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `superpowers-test-driven-development`
- Files: `app/domain/questions/*`, `app/domain/weekly/*`, `app/repositories/questions.py`, `app/repositories/weekly_sets.py`, `app/api/learner.py` weekly slice, `tests/integration/test_question_visibility.py`, `tests/integration/test_weekly_rules.py`
- Action: implement published/current visibility, difficulty/skill/solved filters, weekly deficits/warnings, publish/close/cutoff, retired/void rules, safe learner projections.
- Proof: one published set, no reused questions, close idempotency, competition ranking input, archived access denial, 50-question target/warnings.
- Done: learner receives no answer/reference/hidden data and closed week returns summaries only.
- Dependencies: T04, T05.
- Write scope: question/weekly domain and repositories.

#### T07: SQL run and grading execution contract

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `sd-resilience-failure`
- Files: `app/sandbox/*`, `app/api/learner.py` run slice, `app/domain/submissions/*`, `tests/security/test_sandbox_contract.py`, `tests/integration/test_run_submit.py`
- Action: implement server-owned dataset resolution, bounded run contract, submission state machine, hidden-test-safe result, and adapter boundary to isolated execution service. Keep current SQLite engine only as explicitly marked non-production test adapter.
- Proof: dataset allowlist, timeout/row/result limits, unauthorized question access, hidden result secrecy, submission transitions, cutoff/conflict behavior.
- Done: arbitrary client DDL/seed/database URL cannot reach target execution; production gate blocks deployment if isolated executor is absent.
- Dependencies: T05, T06.
- Write scope: sandbox/submission backend only.

#### T08: Submission idempotency, history, progress, leaderboard, reports

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `superpowers-test-driven-development`
- Files: `app/api/learner.py` remaining slices, `app/domain/reports/*`, repositories for submissions/reports, `tests/integration/test_progress_leaderboard.py`, `tests/security/test_idor.py`
- Action: implement submit polling/history, `Idempotency-Key`, report duplicate conflict, progress, ranking ties, week summaries, ownership checks.
- Proof: same key/payload returns same resource; changed payload returns `409`; solved counts/rank ties/void exclusion and non-resetting progress match design.
- Done: all learner OpenAPI paths have contract tests and ownership enforcement.
- Dependencies: T06, T07.
- Write scope: learner submission/progress/report backend.

### Wave 3 — durable jobs and AI pipeline

#### T09: Durable worker and job lifecycle

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `sd-task-scheduling`
- Files: `app/worker/*`, `app/repositories/generation_jobs.py`, job routes in `app/api/admin.py`, `tests/worker/*`, `docs/sqlarena/worker-operations.md`
- Action: implement PostgreSQL claim with lease/fence, heartbeat, retries, cancellation, dead-letter, idempotent handlers, job detail/counts.
- Proof: two workers cannot commit same fence; lease expiry recovery; retry/backoff; duplicate job request; cancellation; worker restart.
- Done: no process-memory `_tasks` remains for durable behavior.
- Dependencies: T01, T02, T03, T04.
- Write scope: worker/job backend.

#### T10: Anthropic provider and generation quality gates

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `claude-api`
- Files: `app/llm/*`, `llm_gateway.py`, `pipeline.py`, `tests/test_llm_gateway.py`, `tests/integration/test_generation.py`, `.env.example`
- Action: move compatible generator logic behind durable job service; implement Anthropic env contract, provider errors, budget/rate/concurrency guards, prompt/model versioning, Model A/B/checklist validation, clarity/novelty/semantic/evidence gates, human-review fallback.
- Proof: mocked provider cases, budget exhaustion, malformed output, retry cap, model/prompt persistence, unstable evidence remains `needs_human`, no secret leakage.
- Done: generation is admin-only and durable; current prototype validation is reused only through typed gates.
- Dependencies: T05, T06, T09.
- Write scope: LLM/generation backend and provider tests.

#### T11: Draft moderation and atomic approval

- Profile: `dev-be`
- Agent: `dev-be-worker`
- Primary skill: `superpowers-test-driven-development`
- Files: `app/domain/questions/review.py`, review routes in `app/api/admin.py`, repositories for drafts/evidence/audit, `tests/integration/test_approval.py`, `tests/security/test_admin_review.py`
- Action: implement review lock/lease, selected Model B run, rerun blueprint/code gates, test-case evidence, atomic approve/reject, retire/restore.
- Proof: concurrent reviewer conflict, missing evidence stays `needs_human`, approval commits question/test cases/audit atomically, rejected transaction leaves no published question.
- Done: admin cannot approve by submitting arbitrary SQL; approval references selected run ID only.
- Dependencies: T09, T10.
- Write scope: review/approval backend.

### Wave 4 — frontend product

#### T12: Frontend platform and auth/session client

- Profile: `dev-fe`
- Agent: `dev-fe-worker`
- Primary skill: `superpowers-test-driven-development`
- Files: `frontend/src/app/*`, `frontend/src/api/*`, `frontend/src/auth/*`, `frontend/src/features/auth/*`, `frontend/src/components/*`, `frontend/src/test/auth/*`, `frontend/package.json`, `frontend/vite.config.ts`
- Action: add route tree, typed client, in-memory access JWT, refresh retry, public/protected/admin guards, auth forms, global loading/error/session-expired states.
- Proof: build/typecheck, no token in Web Storage, 401 refresh path, locked/role change handling, cookie not readable by JS.
- Done: auth routes work against real API contract, not mock success data.
- Dependencies: T04.
- Write scope: frontend platform/auth only.

#### T13: Learner UI

- Profile: `dev-fe`
- Agent: `dev-fe-worker`
- Primary skill: `design-html`
- Files: `frontend/src/features/learner/*`, `frontend/src/styles/*`, learner route registrations, `frontend/src/test/learner/*`
- Action: implement weekly, practice/run/submit/poll, history, progress, leaderboard, weeks, profile, report screens; preserve flat colour palette and accessibility requirements.
- Proof: browser smoke with real API, loading/empty/error states, hidden result absence, idempotent submit UX, responsive keyboard interaction.
- Done: all learner MVP screens are usable and no placeholder content remains.
- Dependencies: T06–T08, T12.
- Write scope: learner frontend features/styles.

#### T14: Admin UI and dataset import UI

- Profile: `dev-fe`
- Agent: `dev-fe-worker`
- Primary skill: `design-html`
- Files: `frontend/src/features/admin/*`, admin route registrations, `frontend/src/test/admin/*`
- Action: implement users, catalog, drafts, generation jobs, weekly sets, reports, import review/promotion, confirmations, audit visibility, resumable job monitoring.
- Proof: browser smoke with admin fixtures, forbidden learner access, upload validation messages, conflict/retry states, publish/close confirmation.
- Done: admin MVP operations map to working API endpoints and durable job state.
- Dependencies: T05, T09–T11, T12.
- Write scope: admin frontend features.

### Wave 5 — deploy, hardening, integration

#### T15: Local/prod deployment boundary

- Profile: `devops`
- Agent: `devops-worker`
- Primary skill: `setup-deploy`
- Files: `Dockerfile`, `docker-compose.yml`, `vercel.json`, root `package.json`, `.env.example`, scripts, `docs/sqlarena/vercel-boundary.md`, `docs/sqlarena/rollback.md`
- Action: make local API/worker/PostgreSQL/frontend commands work; configure Vercel static/API boundary; remove ephemeral SQLite/task assumptions; add health/readiness checks and rollback runbook.
- Proof: clean checkout Compose smoke, Vercel build, API rewrite test, migration gate, secret scan, worker absence on Vercel explicitly verified.
- Done: deployment documentation states what Vercel does and cannot do; no production claim without external DB/worker/executor.
- Dependencies: T01, T04, T09, T12.
- Write scope: deployment/config/docs only.

#### T16: Contract/security/integration verification

- Profile: `dev-orchestration`
- Agent: `dev-orchestration-agent`
- Primary skill: `vc-test-coverage-plan`
- Files: `tests/contract/*`, `tests/security/*`, `tests/integration/*`, `tests/worker/*`, `frontend/src/test/*`, `docs/sqlarena/test-matrix.md`
- Action: run full gates, inspect route/schema drift, test auth matrix, IDOR, CSRF/CORS, token secrecy, sandbox limits, idempotency, fencing, migrations, Vercel boundary, frontend flows.
- Proof: exact commands and results recorded; failures route to max two fix rounds.
- Done: all acceptance criteria either pass with evidence or are explicitly blocked for user decision; no `DONE` claim from worker.
- Dependencies: T01–T15.
- Write scope: tests and verification report only.

## Task lifecycle and review ownership

Every task follows:

`PLANNED -> APPROVED -> IMPLEMENTING -> READY_FOR_REVIEW -> REVIEW_PASSED -> INTEGRATING -> VERIFYING -> VERIFIED -> DOCS_SYNCED -> DONE`

Side states: `CHANGES_REQUESTED`, `FIXING`, `BLOCKED`, `DEVIATION_PROPOSED`.

Task metadata must include task ID, profile, agent, one primary skill, wave, dependencies, exact write scope, worktree, test gate, stop rule, report path, reviewer, fixer, verifier, and documentation owner.

Default ownership:

- Implementation: named task agent.
- Review: `dev-orchestration-agent`, primary skill `review`.
- Fix: original task agent, same primary skill, maximum two fix rounds.
- Verification: `dev-orchestration-agent`, primary skill `superpowers-verification-before-completion`.
- Shared integration/docs: `dev-orchestration-agent` only.
- Reports: `/Users/nguynbon03/Desktop/Đồ Án Ptit/agents/reports/<TASK_ID>.md`.

Stop immediately on secret exposure, destructive migration, unresolved contract change, overlapping write scope, missing dependency, failed security gate, or production action without explicit approval.

## Test gates

### Focused gates by wave

- Wave 1: migration from empty DB and seeded DB; repository transaction/constraint tests.
- Wave 2: auth matrix; OpenAPI route/status/error tests; dataset allowlist; run/submit ownership and secrecy; weekly rules.
- Wave 3: worker lease/fence/retry/idempotency; provider mocks; budget guard; approval atomicity.
- Wave 4: frontend typecheck/build; browser auth, learner, admin smoke; accessibility keyboard/focus checks.
- Wave 5: Compose smoke; Vercel build/rewrite; secret scan; full contract/security/integration suite.

### Required high-risk coverage

| Area | Minimum tier | Proof |
|---|---|---|
| Auth/session/RBAC | Hybrid | PostgreSQL integration plus HTTP contract/security tests |
| Migrations/data writes | Hybrid | clean and seeded PostgreSQL migration runs |
| Public API/OpenAPI | Fully automated plus hybrid | contract suite plus live API with PostgreSQL |
| Secrets/cookies/CSRF/CORS | Fully automated plus hybrid | response/header/log assertions and deployed-like origin test |
| SQL sandbox | Hybrid | isolated executor fixture; MVP blocks production if unavailable |
| Worker/fencing/idempotency | Hybrid | two-worker PostgreSQL test and restart/lease scenarios |
| Vercel/runtime boundary | Hybrid | build/rewrite smoke with external service configuration |
| Upload/import | Hybrid | real parser fixture and failed-promotion rollback |

Run existing legacy tests during transition, but do not accept them as proof of target security or PostgreSQL behavior. Preserve and adapt useful checks from:

- `tests/test_web.py`
- `tests/test_execution_engine.py`
- `tests/test_llm_gateway.py`
- `tests/test_semantic_checker.py`
- `tests/test_clarity_checker.py`
- `tests/test_novelty_checker.py`

## Acceptance criteria

### MVP functional

1. Clean checkout starts API, worker, PostgreSQL, and frontend using documented local commands.
2. User can register, log in, refresh, log out, change password, and view/update profile.
3. Learner sees only a published current weekly set and paginated safe question projections.
4. Learner can run SQL against a server-selected dataset and receive bounded public results.
5. Learner can submit once or retry with same idempotency key, poll result, and view owned history.
6. Grading state transitions are durable and recover after worker restart.
7. Progress, leaderboard ranking, week history, report creation, and duplicate-report conflict match design rules.
8. Admin can manage users, import a dataset, inspect questions/drafts, approve/reject with evidence, create/monitor generation jobs, manage weekly sets, and resolve/dismiss reports.
9. Approval uses selected run ID and atomic question/test-case/audit commit.
10. Existing generator/clarity/novelty/semantic capabilities either operate through target generation jobs or are explicitly retired; no duplicate unsafe path remains.
11. All frontend routes have real API wiring, no fake placeholder success, and required loading/empty/error states.

### Security

12. Anonymous access to protected data/actions returns target `401`; insufficient role returns `403`; ownership violations do not disclose resource existence beyond contract rules.
13. Locked users are denied and role/status changes take effect without stale authorization.
14. Refresh cookies, rotation, replay detection, logout, reset non-disclosure, CSRF, CORS, and access-token memory rules pass tests.
15. Learner responses never expose reference SQL, expected output, hidden tests, blueprint, review notes, provider output, or secrets.
16. SQL execution never trusts client DDL/seed/database URL and production gate requires isolated executor.
17. Uploads and generation obey size, rate, concurrency, budget, timeout, and audit rules.

### Operations

18. PostgreSQL migrations and seeds are repeatable and guarded against wrong environments.
19. Job state, lease, retry, cancellation, and audit records survive process restart.
20. Vercel deployment is documented as frontend/bounded API only; external PostgreSQL, worker, storage, and executor are explicit.
21. Rollback procedure exists for app release, failed migration, failed import, bad prompt/model activation, and weekly publish conflict.
22. Test reports contain exact commands/results; no unresolved critical/high security findings remain.

## Dependencies

### Required before implementation

- User approval of this DRAFT revision.
- PostgreSQL 15+ local and target managed service decision.
- One selected Python PostgreSQL access style: `asyncpg` repositories or SQLAlchemy async; do not mix without approval.
- Object storage choice for production uploads; MVP may use controlled local/Compose volume only for local use.
- Isolated SQL executor design and deployment target before production sandbox claim.
- Access-token signing key and refresh-cookie policy supplied through secret manager/environment, never Git.
- Anthropic account/model/base URL and budget owner; tests must work without live credentials.

### Optional after MVP

- Redis rate limiting after measured PostgreSQL limiter capacity.
- Email provider and verification/reset delivery.
- Managed sandbox fleet and autoscaling.
- Observability vendor integration.

## Rollback

- Application rollback: redeploy previous API/worker/frontend artifacts; keep backward-compatible API during migration window.
- Migration rollback: use tested compensating migration; never drop production tables manually. Stop release if backward compatibility is not proven.
- Import rollback: mark imported dataset version inactive and restore prior active version; retain manifest and audit trail.
- Generation rollback: disable job creation, stop worker generation handler, deactivate bad prompt/model version, preserve evidence.
- Weekly rollback: before cutoff, revert unpublished draft transaction; after publish, use target void/current-set conflict rules, never delete learner history.
- Security incident: revoke refresh-token families, disable affected routes/provider, rotate secrets outside Git, preserve redacted audit evidence.
- Vercel rollback: revert frontend/API artifact only; do not treat Vercel rollback as database/worker rollback.

## Plan review and stop rules

Goal-backward review:

- Every acceptance criterion maps to one or more WBS tasks: T01–T16.
- Every task names exact files/modules, action, proof, done condition, dependencies, profile, agent, and one primary skill.
- Dependencies are acyclic: Wave 0 -> Wave 1 -> Wave 2 -> Wave 3/4 -> Wave 5.
- Shared contracts and root integration files have one owner.
- API contracts are wired to repositories, services, worker state, and frontend routes.
- Selected profile, agent, and skill names exist in discovered metadata or supplied runtime registry.
- No placeholder implementation is accepted; known production gaps are named and gated.
- Existing `APPROVED` plan status remains unchanged. This revision remains `DRAFT` until explicit user approval.

## Handoff

After explicit approval, update the root plan revision marker to `status: APPROVED` without deleting the historical narrower approval, create the task manifest and reports directory, freeze `docs/sqlarena/*`, then dispatch only Wave 0/T00. Do not dispatch implementation workers before contract approval.

Exact orchestrator command after approval:

```text
Use dev-orchestration-agent. Read /Users/nguynbon03/Desktop/Đồ Án Ptit/CLAUDE.md, /Users/nguynbon03/Desktop/Đồ Án Ptit/plan.md, all frozen docs/sqlarena contracts, WBS, handoff, and agent manifest. Verify explicit APPROVED status, disjoint scopes, and dependencies. Dispatch only the next approved wave; stop on deviation, secret exposure, destructive migration, or failed security gate.
```

---

# Mongo Atlas + RBAC + Admin LLM Implementation Plan

revision_status: APPROVED
approval_required: satisfied by user approval on 2026-10-11
created_from_skills: vc-scout, vc-plan-discovery fallback, superpowers-writing-plans

## Goal

Ship the current SQLArena prototype as a MongoDB-backed web app: learners and admins log in with roles, admins configure server-side LLM settings, upload/import documents, trigger question generation through the configured Anthropic-compatible proxy, review generated questions, and learners practice with safe projections. Deploy target is `https://doanptitb22.vercel.app/` with secrets supplied only through Vercel and local `.env`.

## Current evidence

- Backend entrypoint: `main.py` currently owns FastAPI routes, static serving, auth endpoints, legacy generation, question listing, stats, and SQL verification.
- Auth helpers: `auth.py` uses stdlib `hashlib.scrypt` password hashes and JWT access tokens from `JWT_SECRET_KEY`.
- Mongo seam: `mongo_store.py` already has MongoDB connection, memory fallback, users, questions, documents, challenges, jobs, and indexes.
- LLM seam: `llm_gateway.py` already supports Anthropic-compatible `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`, and `ANTHROPIC_DEFAULT_OPUS_MODEL`.
- Generation seam: `pipeline.py` already calls `LLMGateway`, validates clarity/novelty/semantic/execution, and persists to SQLite `QuestionBank`.
- Frontend: `frontend/src/main.tsx` is a single React file calling `/api/stats`, `/api/questions`, `/api/generate`, `/api/tasks`, `/api/verify-sql`; it has no token/session handling yet.
- Design references: `/Users/nguynbon03/Downloads/Thiết kế v1`, `v2`, `v3` contain `auth.html`, `learner.html`, `admin.html`; all are offline prototype HTML with SQLArena palette and the weekly progress card shown by user.
- Vercel boundary: `vercel.json` routes `/api/(.*)` to `api/index.py`; `api/index.py` strips `/api`; `main.py` also strips `/api`, so prefix behavior must be normalized.
- Test proof before this DRAFT: `JWT_SECRET_KEY=test-secret python -m pytest -q` passed `50` tests after bounded auth slice.

## Secret and Atlas security decision

The Anthropic-compatible token pasted in chat is considered exposed. Rotate/revoke it before public deployment. Do not commit it, log it, echo it in tests, or write it into `plan.md`, `.env.example`, README, screenshots, fixtures, or Vercel files.

MongoDB Atlas public connectivity decision:

- Local development: keep `42.116.223.28/32` or current developer IP in Atlas Network Access.
- Vercel production: because Vercel serverless outbound IP is not stable without an enterprise/static egress product, Atlas Network Access may need `0.0.0.0/0` for this MVP. Compensating controls are mandatory: strong generated DB password, least-privilege database user scoped to the SQLArena database, TLS SRV URI, no admin database role, no shared credentials, rotate on exposure, and app-level auth/RBAC.
- Preferred production upgrade: use static egress/proxy/VPC peering where available, then replace `0.0.0.0/0` with exact egress CIDRs.
- Connection string shape only:

```text
MONGO_URI=mongodb+srv://<db_user>:<url_encoded_password>@doanptit.dhzzvgo.mongodb.net/sqlarena?retryWrites=true&w=majority&appName=doanptit
MONGO_DB_NAME=sqlarena
```

Never store real `db_password` in Git. Configure `MONGO_URI`, `MONGO_DB_NAME`, `JWT_SECRET_KEY`, `AI_PROVIDER`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, and `ANTHROPIC_DEFAULT_OPUS_MODEL` in Vercel Project Settings → Environment Variables and local `.env` only.

## Non-goals for this revision

- No PostgreSQL migration in this revision.
- No full durable worker platform before Mongo job records work.
- No browser-side LLM key or provider URL control.
- No public unauthenticated generation, stats, question internals, answer SQL, hidden expected output, or admin data.
- No live secret test using the pasted token; use mock provider tests first, then user-run manual smoke with rotated secret.
- No deployment action until user explicitly approves deploy and confirms Vercel env vars are set.

## Target Mongo collections

Minimum collections and ownership:

- `users`: email, password_hash, role `learner|admin`, status `active|locked`, display_name, created_at, updated_at.
- `sessions` optional after MVP access-token flow: refresh token family, hashed token, revoked_at, replay flags.
- `settings`: server-side LLM settings metadata. Store base URL/model/budget flags; store secret reference or encrypted token, never public DTO.
- `documents`: uploaded source metadata, checksum, parsed text preview, type, status, uploader, created_at.
- `imports`: immutable import manifest, parser result, source document IDs, row counts, validation errors, promotion status.
- `questions`: generated/manual question records, status `draft|pending_review|approved|rejected|archived`, learner-safe fields, admin-only answer fields, source document/job IDs.
- `generation_jobs`: requested_by, provider snapshot, prompt params, document IDs, status `queued|running|succeeded|failed`, progress, safe error code, created_at, updated_at.
- `audit_logs`: actor, action, resource, before/after summary, request_id, created_at.
- `weekly_sets`: week number, status `draft|active|closed`, question_ids, start/end, publish audit.
- `submissions`: user_id, question_id, sql, state, result summary, timestamps.
- `progress`: user_id, solved question IDs or aggregate counters, weekly progress.

Indexes required in `mongo_store.py`:

- unique `users.email`
- compound `questions.status,difficulty,topic,created_at`
- unique `documents.checksum`
- compound `generation_jobs.status,created_at`
- compound `audit_logs.actor_id,created_at`
- compound `weekly_sets.status,number`
- unique `submissions.user_id,question_id,created_at` only if idempotency design needs it later

## API surface for this revision

Auth:

- `POST /auth/register`
- `POST /auth/login`
- `GET /me`
- `POST /auth/logout` may be client-side token discard for MVP if no refresh cookie yet.

Learner:

- `GET /questions`: requires learner/admin; learners only receive approved projection.
- `GET /questions/{id}`: requires learner/admin; learners only approved projection, never `answer_sql`, `expected_output`, `seed_sql`, hidden checks, provider metadata.
- `GET /weekly/current`: returns active week, progress card data matching user screenshot.
- `GET /me/progress`: returns completed/total/percentage.

Admin:

- `GET /admin/stats`
- `GET /admin/users`
- `PATCH /admin/users/{id}` lock/role/status with self-demotion guard.
- `GET /admin/settings/llm`: returns non-secret config summary only.
- `PUT /admin/settings/llm`: accepts base URL/model/token; stores token server-side only, records audit; response redacts token.
- `POST /admin/llm/test`: calls configured provider with tiny prompt and redacted logging. Requires explicit admin action.
- `POST /admin/documents`: upload `.csv`, `.xlsx`, `.json`, `.md`, `.txt`, `.pdf` with size/type/checksum checks.
- `GET /admin/documents`
- `POST /admin/generation-jobs`: document IDs + quantity/difficulty/topic; creates Mongo job and runs bounded generation.
- `GET /admin/generation-jobs/{id}`
- `PATCH /admin/questions/{id}/status`: approve/reject/archive.

Compatibility:

- Keep `/health` public.
- Move legacy `/stats` to admin-only or alias it to `/admin/stats`.
- Keep `/verify-sql` admin-only for this prototype; learner run/submit comes in a later sandbox slice.

## File map

Backend files:

- Modify `main.py`: route grouping, auth dependencies, admin/learner endpoints, prefix normalization, remove unused imports, no duplicate `/api` strip.
- Modify `auth.py`: add role constants, optional logout stub, clearer token expiry config, tests around locked users.
- Modify `mongo_store.py`: expand collections, indexes, CRUD methods, Mongo-only production guard, no silent memory fallback when `ENV=production` or `VERCEL=1`.
- Modify `llm_gateway.py`: allow settings object override, support Anthropic-compatible proxy URL `.../v1` by appending `/messages`, redact secrets in errors/logs.
- Modify `pipeline.py`: accept `LLMGateway` and source document text; write generated questions/jobs to Mongo instead of SQLite for target path.
- Create `tests/test_auth_rbac.py`: role/lock/admin matrix.
- Create `tests/test_mongo_store.py`: unique users, indexes, question projection, job lifecycle using memory store and optional Mongo integration marker.
- Create `tests/test_admin_llm_settings.py`: redaction, settings save, mock provider test call.
- Create `tests/test_document_import.py`: CSV/XLSX/JSON/MD/TXT parser, unsupported type, duplicate checksum.
- Create `tests/test_generation_jobs.py`: job create/status, provider failure, generated question saved in Mongo.
- Modify `.env.example`: sanitized env names only.
- Modify `README.md`: Atlas/Vercel setup, no real secrets, exact env var list.
- Modify `scripts/create_admin.py`: works with Atlas URI, fails closed if password weak.

Frontend files:

- Replace or split `frontend/src/main.tsx` into minimal focused files only if needed:
  - `frontend/src/api.ts`: token-aware fetch wrapper.
  - `frontend/src/auth.tsx`: login/register/session state.
  - `frontend/src/App.tsx`: route/tab shell.
  - `frontend/src/admin.tsx`: admin dashboard/settings/import/generation/review slices.
  - `frontend/src/learner.tsx`: weekly card/questions/progress slices.
  - `frontend/src/styles.css`: adapt design v1/v2/v3 palette/components.
- Keep no new routing dependency unless manual tab routing becomes unmaintainable.
- Use design references from `/Users/nguynbon03/Downloads/Thiết kế v1`, `v2`, `v3`; implement real API wiring, not copied demo JS state.

DevOps files:

- Modify `vercel.json`: ensure single `/api` prefix behavior.
- Modify `api/index.py`: keep or remove prefix stripping, but only one layer strips.
- Modify root `package.json` only if Vercel build command needs frontend/static integration.
- Document Vercel env vars and Atlas Network Access in README; do not store values.

## Workstreams and agents

### M00 — Freeze Mongo/Vercel contract

- Profile: `dev-analys` + `dev-build`
- Skill: `superpowers-writing-plans`
- Agent: main session or `dev-build-worker`
- Files: `plan.md`, `README.md` contract section only
- Action: finalize this DRAFT, confirm Mongo Atlas public-access decision, confirm secret rotation, confirm deployment URL.
- Proof: plan has DRAFT marker, env names are sanitized, no secrets in diff.
- Dependencies: user approval.
- Stop rule: any real token/password appears in tracked file.

### M01 — Mongo store foundations

- Profile: `dev-be`
- Skill: `superpowers-test-driven-development`
- Agent: `dev-be-worker`
- Files: `mongo_store.py`, `tests/test_mongo_store.py`, `.env.example`
- Action: add collections/indexes/CRUD for users, settings, documents, imports, questions, jobs, weekly, progress, audit. Production mode must fail if `MONGO_URI` missing or unreachable.
- Proof: `JWT_SECRET_KEY=test-secret pytest -q tests/test_mongo_store.py` and full suite.
- Dependencies: M00.
- Write scope: Mongo persistence only.

### M02 — RBAC and route split

- Profile: `dev-be`
- Skill: `superpowers-test-driven-development`
- Agent: `dev-be-worker`
- Files: `auth.py`, `main.py`, `tests/test_auth_rbac.py`, `tests/test_web.py`
- Action: enforce learner/admin dependencies, locked user denial, admin-only stats/generation/settings/import, learner-safe projections, self-demotion guard.
- Proof: anonymous `401`, learner `403` on admin routes, admin success, locked user denied, no learner answer fields.
- Dependencies: M01.
- Write scope: auth/route contracts only.

### M03 — Admin LLM settings and proxy test

- Profile: `dev-be`
- Skill: `claude-api`
- Agent: `dev-be-worker`
- Files: `llm_gateway.py`, `main.py`, `mongo_store.py`, `tests/test_admin_llm_settings.py`
- Action: store provider config metadata in Mongo, accept token through admin-only endpoint or env, redact responses/logs, add mockable provider test route.
- Required env shape:

```text
AI_PROVIDER=anthropic
ANTHROPIC_BASE_URL=<rotated_proxy_base_url_without_/messages_or_with_/v1>
ANTHROPIC_AUTH_TOKEN=<rotated_secret>
ANTHROPIC_DEFAULT_OPUS_MODEL=ZPro-GPT-Claude
```

- Proof: mock provider call passes, invalid auth maps to safe error, token never appears in JSON/log assertions.
- Dependencies: M01, M02.
- Write scope: LLM settings/provider only.

### M04 — Document import and source catalog

- Profile: `dev-be`
- Skill: `superpowers-test-driven-development`
- Agent: `dev-be-worker`
- Files: `main.py`, `mongo_store.py`, `tests/test_document_import.py`, `requirements.txt`
- Action: implement admin upload for `.csv`, `.xlsx`, `.json`, `.md`, `.txt`, `.pdf`; size/type/checksum validation; parsed text stored in `documents`; duplicate checksum returns existing manifest or `409` per final choice.
- Proof: valid fixtures save, unsupported file rejected, duplicate checksum handled, learner cannot upload.
- Dependencies: M02.
- Write scope: documents/import routes only.

### M05 — Mongo-backed generation jobs

- Profile: `dev-be`
- Skill: `superpowers-test-driven-development`
- Agent: `dev-be-worker`
- Files: `pipeline.py`, `llm_gateway.py`, `mongo_store.py`, `main.py`, `tests/test_generation_jobs.py`
- Action: create `generation_jobs`, pass document text into prompts, run bounded sync/background generation, save generated draft questions to Mongo with source job/doc IDs.
- Proof: mock LLM returns JSON, job reaches `succeeded`, question saved as `pending_review`, provider failure marks `failed`, no SQLite target path needed for generated questions.
- Dependencies: M03, M04.
- Write scope: generation/job backend only.

### M06 — Frontend auth + learner UI from design

- Profile: `dev-fe`
- Skill: `design-html`
- Agent: `dev-fe-worker`
- Files: `frontend/src/*`, `frontend/src/styles.css`, `frontend/package.json` if necessary
- Action: implement login/register, memory-only bearer token, learner dashboard/questions/progress/weekly card matching design v1/v2/v3 and screenshot.
- Proof: `npm --prefix frontend run build`; manual smoke with learner cannot see admin nav or answer fields.
- Dependencies: M02.
- Write scope: frontend auth/learner only.

### M07 — Frontend admin UI from design

- Profile: `dev-fe`
- Skill: `design-html`
- Agent: `dev-fe-worker`
- Files: `frontend/src/*`, `frontend/src/styles.css`
- Action: implement admin dashboard users/questions/LLM settings/document import/generation jobs/review UI wired to real API.
- Proof: `npm --prefix frontend run build`; admin can save settings redacted, upload doc, start mock job, review question.
- Dependencies: M03, M04, M05, M06.
- Write scope: frontend admin only.

### M08 — Vercel + Atlas deployment boundary

- Profile: `devops`
- Skill: `setup-deploy`
- Agent: `devops-worker`
- Files: `vercel.json`, `api/index.py`, `README.md`, `.env.example`, `docker-compose.yml` if still used locally
- Action: normalize `/api` prefix, document Vercel env setup, document Atlas network access choice, verify production does not use memory fallback.
- Proof: local `pytest -q`, `npm --prefix frontend run build`, Vercel build log passes; manual smoke against `https://doanptitb22.vercel.app/health` or `/api/health` after user-approved deploy.
- Dependencies: M01–M07.
- Write scope: deploy/config/docs only.

### M09 — Integration/security verification

- Profile: `dev-orchestration`
- Skill: `review` then `superpowers-verification-before-completion`
- Agent: `dev-orchestration-agent`
- Files: tests only plus verification report if needed
- Action: run full backend/frontend checks, review diff for secrets, RBAC, CORS, route prefix, Atlas fallback, provider redaction.
- Proof commands:

```text
JWT_SECRET_KEY=test-secret pytest -q
git diff --check
npm --prefix frontend run build
python -m py_compile main.py auth.py mongo_store.py llm_gateway.py pipeline.py
```

- Dependencies: M01–M08.
- Stop rule: secret in tracked files, public admin route, wildcard CORS with credentials, production memory fallback, learner answer leakage.

## Execution waves

- Wave A: M00 only. Stop for user review.
- Wave B: M01 + M02 backend foundation.
- Wave C: M03 + M04 + M05 backend admin/generation.
- Wave D: M06 + M07 frontend.
- Wave E: M08 + M09 deploy/verify.

Multi-agent execution is approved only after this DRAFT becomes APPROVED. Because files overlap heavily (`main.py`, `mongo_store.py`, `frontend/src/*`), concurrent workers must run by wave and exclusive scope, not all at once.

## Acceptance criteria

1. Vercel app has real login/register against Mongo Atlas.
2. `learner` can list approved questions and weekly/progress card but cannot see admin screens, generation, stats, answer SQL, seed SQL, expected output, or LLM settings.
3. `admin` can manage users, see stats, configure LLM settings with redacted token display, upload documents, start generation job, poll job, review generated questions.
4. Generated questions and uploaded documents persist in Mongo Atlas collections.
5. App works with Vercel env vars; no real secret is in Git.
6. Local tests and frontend build pass.
7. Public Atlas access, if used for Vercel, is documented as MVP tradeoff with least-privilege DB user and rotation requirements.

## Immediate handoff after approval

If user approves this DRAFT, dispatch `dev-orchestration-agent` with this command:

```text
Read /Users/nguynbon03/Desktop/Đồ Án Ptit/plan.md. Verify Mongo Atlas + RBAC + Admin LLM revision_status is APPROVED. Dispatch Wave B only: M01 then M02. Use dev-be-worker with exclusive scopes. Stop before M03 unless M01/M02 tests pass and no secret appears in diff.
```
