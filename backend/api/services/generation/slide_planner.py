import json
from ..gemini_client import generate_structured
from ..templates.prompt_templates import slide_planning_prompt

SLIDE_PLAN_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "slide_index": {"type": "integer"},
            "slide_type": {
                "type": "string",
                "enum": ["title", "overview", "chart", "insight", "comparison",
                         "executive_summary", "recommendation", "data_table"]
            },
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "narrative_hint": {"type": "string"},
            "insight_ids": {"type": "array", "items": {"type": "string"}},
            "bullet_points": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["slide_index", "slide_type", "title", "narrative_hint", "insight_ids"],
    }
}


def plan_slides(insights: list[dict], objectives: dict) -> list[dict]:
    """Use Gemini to design an ordered slide plan from insights and objectives."""
    insights_json = json.dumps(insights, indent=2)
    objectives_json = json.dumps(objectives, indent=2)
    prompt = slide_planning_prompt(insights_json, objectives_json)
    result = generate_structured(prompt, SLIDE_PLAN_SCHEMA, label="plan_slides")
    # Re-index slides starting from 0
    for i, slide in enumerate(result):
        slide['slide_index'] = i
    return result
