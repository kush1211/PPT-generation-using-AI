"""
Gemini client via Vertex AI express mode.
Auth: VERTEX_AI_API_KEY only (no service account / GOOGLE_CLOUD_PROJECT needed).
429 handling per: https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429
"""
from __future__ import annotations

import json
import logging
import random
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from django.conf import settings

logger = logging.getLogger(__name__)

RATE_LIMIT_STATUS = 429


def _backoff_seconds(attempt: int) -> float:
    """Truncated exponential backoff with jitter (per Vertex AI 429 doc)."""
    raw = min(settings.GEMINI_429_INITIAL_BACKOFF * (2 ** attempt), settings.GEMINI_429_MAX_BACKOFF)
    jitter = raw * (0.5 + 0.5 * random.random())
    return max(1.0, jitter)


def _log_429(exc: Exception, attempt: int) -> None:
    msg = str(exc)
    details = getattr(exc, "message", None) or getattr(exc, "details", None)
    extra = f" | details: {details}" if details and str(details) != msg else ""
    logger.warning("429 RESOURCE_EXHAUSTED (attempt %s): %s%s", attempt + 1, msg, extra)


def _is_rate_limit(exc: Exception) -> bool:
    if isinstance(exc, genai_errors.ClientError):
        return (getattr(exc, "code", None) == RATE_LIMIT_STATUS) or (
            "RESOURCE_EXHAUSTED" in (getattr(exc, "status", None) or "")
        )
    return "429" in str(exc).upper() or "RESOURCE_EXHAUSTED" in str(exc).upper()


def _get_client() -> genai.Client:
    api_key = (settings.VERTEX_AI_API_KEY or "").strip()
    if not api_key:
        raise ValueError("Set VERTEX_AI_API_KEY in .env")
    return genai.Client(vertexai=True, api_key=api_key)


def _call_with_retry(client: genai.Client, model: str, contents, config: types.GenerateContentConfig, label: str = "") -> str:
    """Shared retry loop for all generate calls."""
    max_retries = settings.GEMINI_429_MAX_RETRIES
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            usage = getattr(response, "usage_metadata", None)
            if usage:
                print(
                    f"[GEMINI] {label or 'call'} | "
                    f"in={getattr(usage, 'prompt_token_count', '?')} "
                    f"out={getattr(usage, 'candidates_token_count', '?')} "
                    f"total={getattr(usage, 'total_token_count', '?')} tokens",
                    flush=True,
                )
            return response.text or ""
        except Exception as e:
            last_error = e
            if _is_rate_limit(e):
                _log_429(e, attempt)
                if attempt < max_retries - 1:
                    backoff = _backoff_seconds(attempt)
                    logger.warning("Retrying %s/%s in %.1f s...", attempt + 1, max_retries, backoff)
                    time.sleep(backoff)
                else:
                    raise
            else:
                raise
    raise last_error or RuntimeError("Unexpected retry loop exit")


def generate_structured(prompt: str, response_schema: dict, label: str = "structured") -> dict:
    """Call Gemini with a JSON schema to get reliable structured output."""
    client = _get_client()
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=response_schema,
        temperature=0.3,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    text = _call_with_retry(client, settings.GEMINI_MODEL, prompt, config, label=label)
    return json.loads(text.strip())


def generate_text(system_prompt: str, user_prompt: str, temperature: float = 0.7, label: str = "text") -> str:
    """Call Gemini for free-text completion (narrative writing, Q&A)."""
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    return _call_with_retry(client, settings.GEMINI_MODEL, user_prompt, config, label=label).strip()
