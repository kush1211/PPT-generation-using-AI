import json
from ..gemini_client import generate_structured
from ..templates.prompt_templates import objective_inference_prompt

OBJECTIVES_SCHEMA = {
    "type": "object",
    "properties": {
        "presentation_title": {"type": "string"},
        "audience": {"type": "string", "enum": ["executive", "analyst", "client"]},
        "tone": {"type": "string", "enum": ["formal", "consultative", "technical"]},
        "primary_objectives": {
            "type": "array",
            "items": {"type": "string"}
        },
        "key_metrics": {
            "type": "array",
            "items": {"type": "string"}
        },
        "comparison_dimensions": {
            "type": "array",
            "items": {"type": "string"}
        },
    },
    "required": ["presentation_title", "audience", "tone", "primary_objectives", "key_metrics", "comparison_dimensions"],
}


def infer_objectives(rfp_text: str, condensed_repr: str) -> dict:
    """Use Gemini to extract structured objectives from RFP text and data profile."""
    prompt = objective_inference_prompt(rfp_text, condensed_repr)
    result = generate_structured(prompt, OBJECTIVES_SCHEMA)
    return result
