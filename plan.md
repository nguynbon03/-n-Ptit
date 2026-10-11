# SQLArena implementation plan

status: APPROVED

## Intent
Create a complete local/demo web product from the current `Dat` branch, then publish to the user's GitHub repository for Vercel deployment. Remove legacy local LLM runtime integration. Keep all secrets out of Git.

## Evidence
- Current repo: Python FastAPI app; no React/Vue frontend.
- Existing API: `/health`, `/generate`, `/tasks/{task_id}`, `/questions`, `/questions/{question_id}`, `/questions/{question_id}/status`, `/stats`, `/verify-sql`.
- Existing persistence: inspect `question_bank.py`; current app is not the full PostgreSQL/auth platform described in `/Users/nguynbon03/Downloads/Design`.
- Existing LLM providers: Gemini and NVIDIA plus legacy local runtime fallback in `llm_gateway.py`.
- Design package defines a larger target platform in `docs/screens.md` and `api/openapi.yaml`; those contracts are not implemented in this checkout.

## Scope for this execution
1. Remove legacy local runtime code, environment variables, Docker settings, README references, and tests that assert legacy behavior.
2. Add Anthropic-compatible HTTP provider configured only through environment variables:
   - `ANTHROPIC_BASE_URL`
   - `ANTHROPIC_AUTH_TOKEN`
   - `ANTHROPIC_MODEL`
   - `ANTHROPIC_DEFAULT_OPUS_MODEL` as compatibility fallback
   Never commit real values.
3. Preserve Gemini/NVIDIA only if existing code/tests remain coherent; default provider becomes `anthropic`.
4. Add working frontend in the smallest installed/runtime-compatible form. Preferred: Vite + React + TypeScript only if package installation is available; otherwise a static frontend served by FastAPI. Frontend must cover current API capabilities: health/status, generation form and task polling, question list/filter, question detail/status, stats, SQL verification.
5. Apply Lonetrail flat-colour system only:
   - `#5C7F71`, `#802520`, `#BA8530`, `#181818`, `#F5EDDC`, `#B2653B`
   - no CSS gradients, gradient text, or gradient background images
   - responsive layout, keyboard access, visible focus, input text >= 16px on mobile.
6. Add Vercel deployment configuration for the chosen frontend/API layout without claiming external services are provisioned.
7. Add/update tests for provider selection, secret handling/config validation, API/frontend smoke path, and non-gradient style constraint where practical.
8. Update README with local setup, env template, provider setup, Vercel deployment, exact limitations, and commands.

## Explicit non-goals / blockers
- Do not invent full auth, PostgreSQL, weekly-set, learner submissions, admin RBAC, worker queues, or enterprise sandbox from the design package without implementing their backend contracts and migrations. These remain a separate phase.
- Do not commit the token pasted in chat. User must rotate it before deployment.
- Do not deploy or publish secrets.

## Files likely changed
- `llm_gateway.py`
- `.env.example`
- `docker-compose.yml`
- `README.md`
- `requirements.txt` only if needed
- `main.py` and static/frontend files for serving integration
- `tests/test_llm_gateway.py` and related tests
- `vercel.json` and frontend package files if React route is selected
- `plan.md`

## WBS
- W1: provider/config cleanup and tests
- W2: frontend shell and API wiring
- W3: Vercel/local serving integration
- W4: README and deployment env contract
- W5: review, test, local runtime verification
- W6: commit and push to user's `main` repository only after all checks pass

## Verification gates
- `pytest -q`
- frontend build/lint if frontend package is added
- local server `/health`, `/docs`, `/questions`, `/stats`, and a safe `/verify-sql` smoke request
- no legacy local runtime references outside historical git metadata or explicitly archived design text
- no real token in tracked files
- `git diff --check`
- inspect final diff before commit

## Handoff
After implementation, report exact working commands, local URL, Vercel env names, unimplemented design-contract modules, test output, commit SHA, and push result.
