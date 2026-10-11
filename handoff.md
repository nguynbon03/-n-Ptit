# SQLArena handoff

## Snapshot

- Date: 2026-10-12
- Branch: `main`
- Continuation scope: Mongo MVP continuation plan `C01`–`C08` in `plan.md` (`status: APPROVED`). PostgreSQL rewrite remains out of scope.
- Last shipped commit before this pass: `6fed92b feat: close Mongo MVP security, job, and admin gaps (C01-C08)`
- State: `C01`–`C08` implemented, verified locally, committed, and pushed to `main`.

## Completed this pass

| Task | Scope | Outcome |
| --- | --- | --- |
| C01 | `mongo_store.py`, `.env.example`, `tests/test_mongo_store.py` | Production fail-closed; `mode` reports `unavailable` for a configured-but-unreachable URI; duplicate checksum rejected; indexes for users/questions/documents/jobs/audit/settings/submissions |
| C02 | `tests/test_auth_rbac.py` | RBAC/lock/projection contract pinned by tests; no source change needed |
| C03 | `main.py`, `requirements.txt`, `tests/test_document_import.py` | Suffix check before parse, bounded streaming read, duplicate checksum `409`, real newline joins, safe `400` parse errors, `pypdf==6.9.1` declared |
| C04 | `main.py`, `tests/test_generation_jobs.py` | `GET /admin/generation-jobs/{id}`, Mongo-authoritative status, `queued\|running\|succeeded\|failed`, error codes, production gate via `ALLOW_BACKGROUND_JOBS` |
| C05 | `llm_gateway.py`, `main.py`, `mongo_store.py`, `tests/test_admin_llm_settings.py` | `GET`/`PUT /admin/settings/llm`, `POST /admin/llm/test`, write-only token, safe provider error codes, mockable `ping()` |
| C06 | `main.py`, `pipeline.py`, `tests/test_audit.py` | Mongo question records carry job/document/provider/excel source; SQLite marked legacy-only; audit for user/document/generation/review |
| C07 | `frontend/src/{api,auth,admin,learner,main}.tsx`, `styles.css`, `tests/test_frontend_boundary.py` | Memory-only token, `401` clears session, no fake refresh, admin users/settings/job-detail/review-notes/document-status screens |
| C08 | `api/index.py`, `main.py`, `vercel.json`, `README.md`, `.env.example`, `docker-compose.yml`, `tests/test_api_prefix.py` | Single `/api` strip layer in `main.py`; compose requires `MONGO_URI`/`JWT_SECRET_KEY`; Atlas tradeoff and smoke sequence documented |

## Proof run

```text
JWT_SECRET_KEY=test-secret pytest -q
136 passed   (system Python pytest; project `.venv` lacks pytest)

npm --prefix frontend run build
passed (tsc -b + vite build)

python -m py_compile main.py auth.py mongo_store.py llm_gateway.py pipeline.py
git diff --check
passed
```

Live checks against `uvicorn main:app`:

```text
/health and /api/health          -> 200, identical body
/api/api/health                  -> 404  (prefix stripped once)
/apifoo                          -> 404  (no over-eager rewrite)
anonymous /api/questions         -> 401
learner /api/admin/stats         -> 403
learner question keys            -> id, question_text, difficulty, topic, status (no answer/seed/expected)
ENV=production, no MONGO_URI     -> /api/health 503 "MONGO_URI is required when ENV=production or VERCEL is set"
ENV=production, bad MONGO_URI    -> /api/health 503
```

Admin paths through `/api` (in-process ASGI client, memory store):

```text
admin stats/users                -> 200
PUT /api/admin/settings/llm      -> 200, token_hint ********0000, token absent from PUT and GET bodies
duplicate document upload        -> 200 then 409
unsupported suffix               -> 400
audit actions recorded           -> document.upload, settings.llm.update (token absent)
unknown job detail               -> 404
```

## Open items

1. GitHub is synchronized: `main` points to commit `6fed92b` on `origin/main`.
2. Vercel frontend is live at `https://doanptitb22.vercel.app/`, but `/api/health` returns `503` because required server env `MONGO_URI` is not configured. No deployment CLI/session was available to set it safely.
3. Real Mongo proof remains pending. System Python lacks `pymongo`; project `.venv` has `pymongo 4.18.3`. Run checks in `.venv` or deploy with `requirements.txt`.
4. `scripts/create_admin.py` writes to the store its own process selects. With no `MONGO_URI` it seeds an in-memory store that the API process never sees. Creating an admin for a running server requires configured `MONGO_URI`.
5. Provider tokens: rotate anything previously pasted outside a provider console before deploying.

## Explicitly still not done

- No refresh-token rotation, logout endpoint, password reset, or session revocation.
- No durable worker, lease/fencing, retry, or dead-letter. `BackgroundTasks` stays non-durable and is gated off in production.
- No learner submissions, progress persistence, leaderboard, or isolated SQL run service.
- No immutable import manifests or promotion/rollback flow.
- No PostgreSQL target architecture.
- No frontend test runner; the frontend boundary is guarded by a static Python check in `tests/test_frontend_boundary.py`.

## Risks and stop rules

- Never deploy with a provider token taken from chat. Rotate first.
- Never claim Mongo persistence when `health.persistence` is not `mongo`.
- Never expose answer SQL, seed SQL, expected output, hidden checks, or provider secrets to learners.
- Never treat `BackgroundTasks` plus `_tasks` as durable production jobs.
- Stop on a real secret in tracked files, production memory fallback, learner data leakage, or unapproved deployment.

## Resume command

```text
Read /Users/nguynbon03/Desktop/Đồ Án Ptit/CLAUDE.md, plan.md, and handoff.md. main is pushed at 6fed92b. Configure Vercel server env MONGO_URI, MONGO_DB_NAME, JWT_SECRET_KEY, then verify /api/health returns 200 with persistence: mongo before creating admin or enabling generation.
```
