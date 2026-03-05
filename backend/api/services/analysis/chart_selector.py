import json
from ..gemini_client import generate_structured

CHART_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "chart_type": {
            "type": "string",
            "enum": ["bar_chart", "line_chart", "scatter", "pie_chart", "heatmap", "grouped_bar", "waterfall"]
        },
        "x_col": {"type": "string"},
        "y_cols": {"type": "array", "items": {"type": "string"}},
        "color_col": {"type": "string"},
        "filter_expr": {"type": "string"},
        "title": {"type": "string"},
        "sort_by": {"type": "string"},
        "top_n": {"type": "integer"},
    },
    "required": ["chart_type", "x_col", "y_cols", "title"],
}


def select_chart_config(insight: dict, column_map: dict, slide_title: str) -> dict:
    """Use Gemini to determine the best chart configuration for an insight."""
    prompt = f"""You are a data visualization expert. Choose the best chart configuration for this insight.

INSIGHT:
{json.dumps(insight, indent=2)}

AVAILABLE COLUMNS:
Metrics: {column_map.get('metrics', [])}
Dimensions: {column_map.get('dimensions', [])}
Dates: {column_map.get('dates', [])}

SLIDE TITLE: {slide_title}

Return a chart configuration. Use filter_expr as a valid pandas query string if filtering is needed (e.g., "Brand in ['A','B','C']"). Set color_col to null if not needed. Set top_n to limit rows shown (e.g., 5 for top 5)."""

    return generate_structured(prompt, CHART_CONFIG_SCHEMA)
