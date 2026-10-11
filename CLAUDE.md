# SQLArena project rules

## Mandatory reading order

1. `README.md`
2. `handoff.md`
3. `plan.md`
4. Relevant source and tests

## Runtime boundaries

- MongoDB is required for production/Vercel. Never treat `memory` persistence as production success.
- Never commit or print `MONGO_URI`, `JWT_SECRET_KEY`, `ANTHROPIC_AUTH_TOKEN`, or any provider credential.
- Learner responses must exclude answer SQL, seed SQL, expected output, hidden checks, blueprint, review notes, and provider metadata.
- `BackgroundTasks` is local/demo-only. No durable-worker claim.
- PostgreSQL/full SQLArena target remains outside current Mongo MVP scope.

## Deploy Configuration

- Platform: Vercel
- Production URL: `https://doanptitb22.vercel.app/`
- Deploy workflow: auto-deploy on push to `main`
- Deploy status command: HTTP health check
- Merge method: fast-forward or squash, preserving verified commits
- Project type: React/Vite frontend with FastAPI bounded API
- Post-deploy health check: `https://doanptitb22.vercel.app/api/health`

### Custom deploy hooks

- Pre-merge: `JWT_SECRET_KEY=test-secret pytest -q && npm --prefix frontend run build && git diff --check`
- Deploy trigger: push verified commit to `main`
- Deploy status: poll production health URL
- Health check: `/api/health` must return HTTP `200` and JSON `{"persistence":"mongo"}`

### Required Vercel server environment

Configure in Vercel Project Settings, never in Git or frontend build variables:

- `MONGO_URI`
- `MONGO_DB_NAME`
- `JWT_SECRET_KEY`
- `AI_PROVIDER`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_MODEL` or `ANTHROPIC_DEFAULT_OPUS_MODEL`
- `CORS_ORIGINS`

Deployment is blocked until `MONGO_URI`, `MONGO_DB_NAME`, and `JWT_SECRET_KEY` exist. Provider variables are required before generation, not before health/auth.
