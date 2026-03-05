from ..gemini_client import generate_text
from ..templates.prompt_templates import (
    narrative_writing_prompt,
    chat_answer_prompt,
    narrative_rewrite_prompt,
)


def write_narrative(slide_title: str, insight: dict, chart_type: str,
                    narrative_hint: str, audience: str, tone: str) -> str:
    """Generate analyst narrative for a slide."""
    data_points = str(insight.get('data_slice', {}))
    system, user = narrative_writing_prompt(
        slide_title=slide_title,
        insight_finding=insight.get('finding', ''),
        data_points=data_points,
        chart_type=chart_type,
        narrative_hint=narrative_hint,
        audience=audience,
        tone=tone,
    )
    return generate_text(system, user, temperature=0.6)


def answer_question(user_message: str, slide_content: str,
                    condensed_repr: str, objectives_summary: str) -> str:
    """Generate a conversational answer about the presentation."""
    system, user = chat_answer_prompt(
        user_message=user_message,
        slide_content=slide_content,
        condensed_repr=condensed_repr,
        objectives_summary=objectives_summary,
    )
    return generate_text(system, user, temperature=0.5)


def rewrite_for_audience(original_narrative: str, current_audience: str,
                          new_audience: str, data_context: str) -> str:
    """Rewrite a slide narrative for a different audience."""
    system, user = narrative_rewrite_prompt(
        original_narrative=original_narrative,
        current_audience=current_audience,
        new_audience=new_audience,
        data_context=data_context,
    )
    return generate_text(system, user, temperature=0.6)
