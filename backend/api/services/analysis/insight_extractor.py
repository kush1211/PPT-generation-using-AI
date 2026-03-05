import json
from ..gemini_client import generate_structured
from ..templates.prompt_templates import insight_extraction_prompt

INSIGHTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "insight_id": {"type": "string"},
            "title": {"type": "string"},
            "finding": {"type": "string"},
            "magnitude": {"type": "string", "enum": ["high", "medium", "low"]},
            "data_slice": {"type": "object"},
            "chart_hint": {
                "type": "string",
                "enum": ["bar_chart", "line_chart", "scatter", "pie_chart", "heatmap", "grouped_bar", "waterfall"]
            },
            "priority": {"type": "integer"},
        },
        "required": ["insight_id", "title", "finding", "magnitude", "data_slice", "chart_hint", "priority"],
    }
}


def extract_insights(condensed_repr: str, objectives: dict, column_summary: dict) -> list[dict]:
    """Use Gemini to extract key insights from the data profile + objectives."""
    objectives_json = json.dumps(objectives, indent=2)
    stats_json = json.dumps(column_summary, indent=2)[:3000]  # cap size
    prompt = insight_extraction_prompt(condensed_repr, objectives_json, stats_json)
    result = generate_structured(prompt, INSIGHTS_SCHEMA)
    # Sort by priority
    return sorted(result, key=lambda x: x.get('priority', 99))
