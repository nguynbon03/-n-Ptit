"""Vercel Python entrypoint.

The `/api` prefix is stripped in exactly one place: `ApiPrefixMiddleware` in
`main.py`. That middleware is registered last, so it runs outermost and works
both for local `uvicorn main:app` and for Vercel, which forwards the original
`/api/...` path to this function. Do not add a second stripping layer here:
two layers would turn `/api/api/health` into a valid route and break
`/api/<asset>` paths.
"""
from main import app

__all__ = ["app"]
