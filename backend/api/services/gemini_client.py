"""
Gemini client via LangChain + Vertex AI Express mode + LangSmith tracing.

Auth: injects a genai.Client(vertexai=True, api_key=...) directly into
ChatGoogleGenerativeAI so that Vertex AI Express mode (API-key-based auth)
is preserved — same as the original google-genai usage.

LangSmith traces all calls automatically when LANGSMITH_TRACING=true in .env.
429 handling: truncated exponential backoff with jitter.
"""
from __future__ import annotations

import logging
import random
import time

from google import genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from django.conf import settings

logger = logging.getLogger(__name__)


def _backoff_seconds(attempt: int) -> float:
    """Truncated exponential backoff with jitter."""
    raw = min(settings.GEMINI_429_INITIAL_BACKOFF * (2 ** attempt), settings.GEMINI_429_MAX_BACKOFF)
    jitter = raw * (0.5 + 0.5 * random.random())
    return max(1.0, jitter)


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).upper()
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def _get_vertex_client() -> genai.Client:
    """Return a Vertex AI Express client (API-key auth, no service account needed)."""
    api_key = (settings.VERTEX_AI_API_KEY or "").strip()
    if not api_key:
        raise ValueError("Set VERTEX_AI_API_KEY in .env")
    return genai.Client(vertexai=True, api_key=api_key)


def _make_llm(temperature: float = 0.3, **extra) -> ChatGoogleGenerativeAI:
    """Build a ChatGoogleGenerativeAI with a pre-configured Vertex AI Express client."""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        client=_get_vertex_client(),   # injects express-mode client directly
        temperature=temperature,
        thinking_budget=0,
        **extra,
    )


def _invoke_with_retry(llm: ChatGoogleGenerativeAI, messages, label: str) -> str:
    """Shared retry loop — returns raw response content string."""
    max_retries = settings.GEMINI_429_MAX_RETRIES
    last_error: Exception | None = None
    config = RunnableConfig(run_name=label)

    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages, config=config)
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return content or ""
        except Exception as e:
            last_error = e
            if _is_rate_limit(e):
                logger.warning("429 RESOURCE_EXHAUSTED (attempt %s): %s", attempt + 1, e)
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
    """Call Gemini with a JSON schema — returns a parsed dict/list.
    Traced in LangSmith via run_name=label.
    """
    import json

    llm = _make_llm(
        temperature=0.3,
        response_mime_type="application/json",
        response_schema=response_schema,
    )
    text = _invoke_with_retry(llm, prompt, label=label)
    return json.loads(text.strip())


def generate_text(system_prompt: str, user_prompt: str, temperature: float = 0.7, label: str = "text") -> str:
    """Call Gemini for free-text completion.
    Traced in LangSmith via run_name=label.
    """
    llm = _make_llm(temperature=temperature)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    return _invoke_with_retry(llm, messages, label=label).strip()
