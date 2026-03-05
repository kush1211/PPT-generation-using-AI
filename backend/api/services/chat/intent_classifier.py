from ..gemini_client import generate_structured
from ..templates.prompt_templates import intent_classification_prompt

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent_type": {
            "type": "string",
            "enum": ["explain", "add_chart", "rewrite", "filter", "compare", "question", "regenerate"]
        },
        "target_slide_index": {"type": "integer"},
        "subject": {"type": "string"},
        "parameters": {
            "type": "object",
            "properties": {
                "audience": {"type": "string"},
                "filter_expr": {"type": "string"},
                "chart_type": {"type": "string"},
                "comparison_entities": {"type": "array", "items": {"type": "string"}},
            }
        },
    },
    "required": ["intent_type", "target_slide_index", "subject"],
}


def classify_intent(user_message: str, slides: list[dict], chat_history: list[dict]) -> dict:
    """Classify the user's chat message into a structured intent."""
    # Build slide manifest (one line per slide)
    slide_manifest = '\n'.join(
        f"Slide {s['slide_index']}: {s['title']}"
        for s in slides
    )

    # Last 6 messages for context
    recent_history = chat_history[-6:] if len(chat_history) > 6 else chat_history
    history_str = '\n'.join(f"{m['role'].upper()}: {m['content']}" for m in recent_history)

    prompt = intent_classification_prompt(user_message, slide_manifest, history_str)
    result = generate_structured(prompt, INTENT_SCHEMA)

    # Normalize target_slide_index
    if result.get('target_slide_index', -1) == -1:
        result['target_slide_index'] = None

    return result
