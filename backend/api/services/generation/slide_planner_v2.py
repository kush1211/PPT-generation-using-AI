"""Step 7: Slide Planning v2 (single LLM call).

Takes all insights from all groups plus the full brief context and produces
a complete ordered slide plan with visualization_spec for each chart slide.
"""
import logging

from ..gemini_client import generate_structured
from ..templates.pipeline_prompts import slide_planning_prompt_v2

logger = logging.getLogger(__name__)

# Keep the slide schema flat — no nested viz_spec schema to avoid state-explosion error.
# visualization_spec is an untyped object; its structure is enforced by the prompt instead.
_SLIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "slide_index": {"type": "integer"},
        "slide_type": {
            "type": "string",
            "enum": ["title", "overview", "chart", "insight", "comparison",
                     "executive_summary", "recommendation", "data_table"],
        },
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "key_message": {"type": "string"},
        "content_type": {
            "type": "string",
            "enum": ["chart", "bullets", "narrative", "table"],
        },
        "visualization_spec": {"type": "object"},
        "data_points": {"type": "array", "items": {"type": "string"}},
        "bullet_points": {"type": "array", "items": {"type": "string"}},
        "speaker_notes": {"type": "string"},
        "insight_refs": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["slide_index", "slide_type", "title", "key_message", "content_type", "visualization_spec"],
}

_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative_arc": {"type": "string"},
        "executive_summary_bullets": {"type": "array", "items": {"type": "string"}},
        "slides": {
            "type": "array",
            "items": _SLIDE_SCHEMA,
        },
        "appendix_slides": {"type": "array"},
    },
    "required": ["narrative_arc", "slides"],
}


def plan_slides_v2(
    all_insights: dict,
    full_summary: str,
    audience_and_tone: str,
) -> dict:
    """Generate the slide plan from all group insights.

    Args:
        all_insights: {group_id: list[insight_dict]} from Step 6c
        full_summary: BriefDecomposition.full_summary
        audience_and_tone: BriefDecomposition.audience_and_tone

    Returns:
        dict with keys: narrative_arc, executive_summary_bullets, slides, appendix_slides
    """
    prompt = slide_planning_prompt_v2(all_insights, full_summary, audience_and_tone)
    plan = generate_structured(prompt, _PLAN_SCHEMA, label="slide_planning_v2")

    # Normalise slide_index to be 0-based and sequential
    slides = plan.get('slides', [])
    for i, slide in enumerate(slides):
        slide['slide_index'] = i
        slide.setdefault('subtitle', '')
        slide.setdefault('visualization_spec', None)
        slide.setdefault('data_points', [])
        slide.setdefault('bullet_points', [])
        slide.setdefault('speaker_notes', '')
        slide.setdefault('insight_refs', [])

    logger.info(
        "Slide plan: %d slides, narrative_arc=%r",
        len(slides),
        plan.get('narrative_arc', '')[:80],
    )
    return plan
