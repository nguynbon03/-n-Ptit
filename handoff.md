# SQLArena handoff

## Current branch

`feature/mongo-rbac-ui`

## Completed in this pass

- Approved Mongo Atlas + RBAC plan in `plan.md`.
- Added Mongo-backed API foundations:
  - auth register/login/me already active;
  - questions now read/update via `mongo_store.py`;
  - admin stats/users/documents/generation-jobs routes;
  - weekly current route;
  - generation jobs saved to Mongo job records;
  - generated SQLite legacy questions sync back into Mongo questions for current pipeline compatibility.
- Expanded `mongo_store.py` with users listing, user lookup, jobs, admin stats, settings/audit collection slots, indexes.
- Replaced React UI with role-based auth/learner/admin shell using SQLArena design palette and weekly challenge card.
- Kept secrets out of repo.

## Verification

- `JWT_SECRET_KEY=test-secret python -m pytest -q` → 50 passed
- `npm --prefix frontend run build` → passed
- `git diff --check && python -m py_compile main.py mongo_store.py auth.py` → passed

## Next phases

1. Set Vercel env vars: `MONGO_URI`, `MONGO_DB_NAME`, `JWT_SECRET_KEY`, `AI_PROVIDER`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_DEFAULT_OPUS_MODEL`.
2. Redeploy Vercel.
3. Smoke test `/api/health` returns `persistence: mongo`.
4. Create admin user with `scripts/create_admin.py` using local env or add admin in Mongo.
5. Next code phase: real admin LLM settings storage and document-driven prompt injection.

## Safety

The token pasted in chat must be rotated before use. Do not commit real env values.
