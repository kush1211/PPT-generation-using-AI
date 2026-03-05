import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from google import genai
from google.genai import types
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"


def _get_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=10, max=120),
    reraise=True,
)
def generate_structured(prompt: str, response_schema: dict) -> dict:
    """Call Gemini with a JSON schema to get reliable structured output."""
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.3,
        ),
    )
    return json.loads(response.text.strip())


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=10, max=120),
    reraise=True,
)
def generate_text(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """Call Gemini for free-text completion (narrative writing, Q&A)."""
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=f"{system_prompt}\n\n{user_prompt}",
        config=types.GenerateContentConfig(
            temperature=temperature,
        ),
    )
    return response.text.strip()
