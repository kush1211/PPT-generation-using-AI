from ..gemini_client import generate_structured
from ..templates.prompt_templates import objective_inference_prompt

ENRICHED_SCHEMA = {
    "type": "object",
    "properties": {
        "dataset_context": {"type": "string"},
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "classification": {
                        "type": "string",
                        "enum": ["metric", "dimension", "date", "id"],
                    },
                    "description": {"type": "string"},
                },
                "required": ["column", "classification", "description"],
            },
        },
        "presentation_title": {"type": "string"},
        "audience": {"type": "string", "enum": ["executive", "analyst", "client"]},
        "tone": {"type": "string", "enum": ["formal", "consultative", "technical"]},
        "primary_objectives": {"type": "array", "items": {"type": "string"}},
        "key_metrics": {"type": "array", "items": {"type": "string"}},
        "comparison_dimensions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "dataset_context", "columns", "presentation_title", "audience", "tone",
        "primary_objectives", "key_metrics", "comparison_dimensions",
    ],
}


def infer_objectives(rfp_text: str, condensed_repr: str, column_samples: list[dict]) -> dict:
    """
    Single Gemini call that:
    1. Classifies each column (metric/dimension/date/id) with a business description
    2. Extracts structured presentation objectives
    Returns the full response dict — caller splits it into column_map + objectives.
    """
    prompt = objective_inference_prompt(rfp_text, condensed_repr, column_samples)
    return generate_structured(prompt, ENRICHED_SCHEMA, label="infer_objectives")
