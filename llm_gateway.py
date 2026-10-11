import logging
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv(override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JSON_INSTRUCTION = "\n\nRespond with ONLY valid JSON, no markdown, no explanation."

_REDACTED = "***"


class ProviderError(RuntimeError):
    """Provider failure with a safe code and no secret or payload content."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def classify_provider_error(exc: Exception) -> ProviderError:
    """Map a provider exception to a safe code. Never includes token or body."""
    name = exc.__class__.__name__
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return ProviderError("invalid_auth", "Provider rejected the credential")
    if status == 429:
        return ProviderError("rate_limited", "Provider rate limit reached")
    if status is not None and status >= 500:
        return ProviderError("provider_unavailable", f"Provider returned HTTP {status}")
    if status is not None:
        return ProviderError("provider_error", f"Provider returned HTTP {status}")
    if "Timeout" in name:
        return ProviderError("timeout", "Provider request timed out")
    if "Connect" in name or "Network" in name:
        return ProviderError("network_error", "Provider is unreachable")
    return ProviderError("provider_error", f"Provider call failed ({name})")


class LLMGateway:
    def __init__(self, overrides: dict | None = None):
        self._overrides = {k: v for k, v in (overrides or {}).items() if v not in (None, "")}
        self.provider = self._setting("AI_PROVIDER", "anthropic").strip().lower()

        if self.provider == "anthropic":
            self.base_url = self._build_anthropic_url(
                self._setting("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1/messages")
            )
            self.model = (
                self._setting("ANTHROPIC_MODEL", "").strip()
                or self._setting("ANTHROPIC_DEFAULT_OPUS_MODEL", "").strip()
                or "claude-sonnet-4-6"
            )
            self.api_key = self._setting("ANTHROPIC_AUTH_TOKEN", "").strip() or self._setting(
                "ANTHROPIC_API_KEY", ""
            ).strip()
            if not self.api_key:
                raise RuntimeError(
                    "ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY is required "
                    "when AI_PROVIDER=anthropic"
                )
        elif self.provider == "gemini":
            self.gemini_api_key = self._setting("GEMINI_API_KEY", "")
            self.gemini_model = self._setting("GEMINI_MODEL", "gemini-2.0-flash")
            if not self.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
            self._init_gemini()
        elif self.provider == "nvidia":
            self.base_url = self._setting(
                "NVIDIA_BASE_URL",
                "https://integrate.api.nvidia.com/v1/chat/completions",
            ).rstrip("/")
            self.model = self._setting("NVIDIA_MODEL", "google/gemma-4-31b-it")
            self.api_key = self._setting("NVIDIA_API_KEY", "")
            if not self.api_key:
                raise RuntimeError("NVIDIA_API_KEY is required when AI_PROVIDER=nvidia")
        else:
            raise RuntimeError(
                f"Unsupported AI_PROVIDER={self.provider!r}; use anthropic, gemini, or nvidia"
            )

        logger.info(
            "LLMGateway initialized. provider=%s model=%s",
            self.provider,
            self.gemini_model if self.provider == "gemini" else self.model,
        )

    def _setting(self, key: str, default: str = "") -> str:
        """Server-side settings override env; neither value is ever logged."""
        if key in self._overrides:
            return str(self._overrides[key])
        return os.getenv(key, default)

    def ping(self, timeout: float = 20.0) -> dict:
        """One short provider call used by the admin connectivity test.

        Raises ProviderError with a safe code. Never returns or logs the token.
        """
        if self.provider == "gemini":
            try:
                response = self._gemini_client.generate_content("Reply with OK")
                text = (getattr(response, "text", "") or "").strip()
            except Exception as exc:
                raise classify_provider_error(exc) from exc
            return {"provider": "gemini", "model": self.gemini_model, "sample": text[:80]}

        if self.provider == "anthropic":
            payload = {"model": self.model, "max_tokens": 16, "messages": [{"role": "user", "content": "Reply with OK"}]}
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        else:
            payload = {"model": self.model, "max_tokens": 16, "messages": [{"role": "user", "content": "Reply with OK"}]}
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            response = httpx.post(self.base_url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise classify_provider_error(exc) from exc

        if self.provider == "anthropic":
            sample = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        else:
            sample = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {"provider": self.provider, "model": self.model, "sample": (sample or "").strip()[:80]}

    @staticmethod
    def _build_anthropic_url(raw_url: str) -> str:
        url = raw_url.strip().rstrip("/")
        if url.endswith("/messages"):
            return url
        if url.endswith("/v1"):
            return f"{url}/messages"
        return f"{url}/v1/messages"

    def _init_gemini(self):
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.gemini_api_key)
            self._genai = genai
            self._gemini_client = genai.GenerativeModel(self.gemini_model)
            logger.info("Gemini client ready. model=%s", self.gemini_model)
        except ImportError:
            raise RuntimeError(
                "google-generativeai package not installed. Run: pip install google-generativeai"
            )

    def _generate_gemini(self, prompt: str) -> str:
        for attempt in range(3):
            try:
                response = self._gemini_client.generate_content(prompt)
                return response.text.strip()
            except Exception as exc:
                logger.error("Gemini attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2**attempt)
        return "ERROR: Gemini LLM failed after retries"

    def _generate_anthropic(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": "Follow user instructions exactly. Return no markdown unless requested.",
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "accept": "application/json",
            "content-type": "application/json",
        }
        for attempt in range(3):
            try:
                response = httpx.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=180.0,
                )
                response.raise_for_status()
                content = response.json().get("content", [])
                text = "".join(
                    block.get("text", "") for block in content if block.get("type") == "text"
                )
                if not text:
                    raise ValueError("Anthropic response contained no text content")
                return text.strip()
            except Exception as exc:
                logger.error("Anthropic attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2**attempt)
        return "ERROR: Anthropic LLM failed after retries"

    def _generate_nvidia(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Follow the user instructions exactly. Return no markdown unless requested.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
            "stream": False,
            "temperature": 0.1,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "seed": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        for attempt in range(3):
            try:
                response = httpx.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=180.0,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                logger.error("NVIDIA attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2**attempt)
        return "ERROR: NVIDIA LLM failed after retries"

    def generate(self, task_type: str, prompt: str, expect_json: bool = False) -> str:
        """Generate text for planner, generator, or clarity tasks."""
        if expect_json:
            prompt += JSON_INSTRUCTION

        logger.info(
            "LLM call. provider=%s task=%s expect_json=%s",
            self.provider,
            task_type,
            expect_json,
        )

        if self.provider == "anthropic":
            return self._generate_anthropic(prompt)
        if self.provider == "gemini":
            return self._generate_gemini(prompt)
        return self._generate_nvidia(prompt)
