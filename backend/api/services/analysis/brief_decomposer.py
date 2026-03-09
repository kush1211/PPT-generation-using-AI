"""Step 0: Brief Decomposition.

Decomposes the raw brief (RFP text + data overview) into 4 reusable analytical fields
that are referenced throughout subsequent pipeline steps.
"""
import json
import logging

from ..gemini_client import generate_structured
from ..templates.pipeline_prompts import brief_decomposition_prompt

logger = logging.getLogger(__name__)

_BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "domain_context": {"type": "string"},
        "analytical_questions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 6,
        },
        "audience_and_tone": {"type": "string"},
        "full_summary": {"type": "string"},
        "presentation_title": {"type": "string"},
        "audience": {"type": "string", "enum": ["executive", "analyst", "client"]},
        "tone": {"type": "string", "enum": ["formal", "consultative", "technical"]},
    },
    "required": [
        "domain_context", "analytical_questions", "audience_and_tone",
        "full_summary", "presentation_title", "audience", "tone",
    ],
}


def _build_sheet_metadata_summary(sheet_metadata: dict) -> str:
    """Produce a compact text summary of all sheets for the LLM prompt."""
    lines = []
    for sheet_name, meta in sheet_metadata.items():
        cols = meta.get('columns', [])
        n = meta.get('row_count', '?')
        dtypes = meta.get('inferred_dtypes', {})
        col_desc = ', '.join(f"{c} ({dtypes.get(c, '?')})" for c in cols[:15])
        lines.append(f"Sheet '{sheet_name}' ({n} rows): {col_desc}")
        sample = meta.get('sample_top', [])
        if sample:
            lines.append(f"  Sample: {json.dumps(sample[0])[:200]}")
    return '\n'.join(lines)


def decompose_brief(rfp_text: str, sheet_metadata: dict) -> dict:
    """Decompose the raw brief into 4 analytical fields + title/audience/tone.

    Args:
        rfp_text: Parsed RFP/document text (empty string if no document uploaded)
        sheet_metadata: Per-sheet metadata dict from multi_sheet_loader.extract_sheet_metadata()

    Returns:
        dict with keys:
            domain_context, analytical_questions, audience_and_tone, full_summary,
            presentation_title, audience, tone
    """
    metadata_summary = _build_sheet_metadata_summary(sheet_metadata)
    prompt = brief_decomposition_prompt(rfp_text, metadata_summary)

    result = generate_structured(prompt, _BRIEF_SCHEMA, label="brief_decomposition")

    # Ensure analytical_questions is a list
    if isinstance(result.get('analytical_questions'), str):
        result['analytical_questions'] = [result['analytical_questions']]

    logger.info(
        "Brief decomposition complete: domain=%r, %d questions",
        result.get('domain_context', '')[:50],
        len(result.get('analytical_questions', [])),
    )
    return result
