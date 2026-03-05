import json
import pandas as pd
from ..generation.narrative_writer import answer_question, rewrite_for_audience, write_narrative
from ..generation.chart_builder import build_chart
from ..generation.ppt_builder import build_presentation
from ..analysis.chart_selector import select_chart_config
from ..data_ingestion.data_profiler import dataframe_from_serializable


def handle_chat(intent: dict, project, slides: list, chat_history: list) -> dict:
    """
    Route a classified intent to the appropriate handler.
    Returns: { response_text, updated_slide_index, slide_data (if modified), new_pptx_path }
    """
    intent_type = intent.get('intent_type', 'question')
    target_idx = intent.get('target_slide_index')
    params = intent.get('parameters', {})
    subject = intent.get('subject', '')

    profile = project.data_file.profile if hasattr(project, 'data_file') else {}
    condensed_repr = profile.get('condensed_repr', '')
    objectives = _get_objectives_dict(project)

    if intent_type in ('explain', 'question'):
        return _handle_question(intent, project, slides, condensed_repr, objectives)

    elif intent_type == 'rewrite':
        return _handle_rewrite(intent, project, slides, condensed_repr, objectives)

    elif intent_type == 'add_chart':
        return _handle_add_chart(intent, project, slides, condensed_repr, objectives)

    elif intent_type in ('filter', 'compare'):
        return _handle_filter_compare(intent, project, slides, condensed_repr, objectives)

    else:
        return _handle_question(intent, project, slides, condensed_repr, objectives)


def _handle_question(intent, project, slides, condensed_repr, objectives):
    target_idx = intent.get('target_slide_index')
    user_message = intent.get('_user_message', '')

    slide_content = ''
    if target_idx is not None:
        matching = [s for s in slides if s.get('slide_index') == target_idx]
        if matching:
            s = matching[0]
            slide_content = f"Title: {s.get('title', '')}\nNarrative: {s.get('narrative', '')}"

    objectives_summary = json.dumps(objectives, indent=2)[:500]
    response = answer_question(user_message, slide_content, condensed_repr, objectives_summary)
    return {'response_text': response, 'updated_slide_index': None, 'slide_data': None}


def _handle_rewrite(intent, project, slides, condensed_repr, objectives):
    target_idx = intent.get('target_slide_index')
    params = intent.get('parameters', {})
    new_audience = params.get('audience', 'executive')
    current_audience = objectives.get('audience', 'analyst')
    user_message = intent.get('_user_message', '')

    if target_idx is None:
        return {'response_text': 'Please specify which slide to rewrite.', 'updated_slide_index': None, 'slide_data': None}

    matching = [s for s in slides if s.get('slide_index') == target_idx]
    if not matching:
        return {'response_text': f'Slide {target_idx} not found.', 'updated_slide_index': None, 'slide_data': None}

    slide = matching[0]
    original_narrative = slide.get('narrative', '')
    new_narrative = rewrite_for_audience(original_narrative, current_audience, new_audience, condensed_repr)

    return {
        'response_text': f'Slide {target_idx + 1} narrative has been rewritten for a {new_audience} audience.',
        'updated_slide_index': target_idx,
        'new_narrative': new_narrative,
        'slide_data': {**slide, 'narrative': new_narrative},
    }


def _handle_add_chart(intent, project, slides, condensed_repr, objectives):
    params = intent.get('parameters', {})
    subject = intent.get('subject', '')
    column_map = project.data_file.column_map if hasattr(project, 'data_file') else {}

    # Create a synthetic insight for chart selection
    synthetic_insight = {
        'insight_id': f'chat_{len(slides)}',
        'title': subject,
        'finding': subject,
        'magnitude': 'medium',
        'data_slice': {},
        'chart_hint': params.get('chart_type', 'bar_chart'),
        'priority': len(slides) + 1,
    }

    chart_config = select_chart_config(synthetic_insight, column_map, subject)

    # Build chart
    df = _load_dataframe(project)
    chart_path = build_chart(chart_config, df) if df is not None else ''

    new_slide = {
        'slide_index': len(slides),
        'slide_type': 'chart',
        'title': subject,
        'subtitle': '',
        'narrative': f'Chart added based on your request: {subject}',
        'chart_png': chart_path,
        'bullet_points': [],
        'speaker_notes': '',
        'insight_ids': [],
        'chart_config': chart_config,
    }

    return {
        'response_text': f'New chart slide added: "{subject}"',
        'updated_slide_index': len(slides),
        'slide_data': new_slide,
        'is_new_slide': True,
    }


def _handle_filter_compare(intent, project, slides, condensed_repr, objectives):
    params = intent.get('parameters', {})
    subject = intent.get('subject', '')
    filter_expr = params.get('filter_expr', '')
    entities = params.get('comparison_entities', [])
    column_map = project.data_file.column_map if hasattr(project, 'data_file') else {}

    # Build filter expression from entities if not provided
    if not filter_expr and entities and column_map.get('dimensions'):
        dim = column_map['dimensions'][0]
        entities_str = ', '.join(f"'{e}'" for e in entities)
        filter_expr = f"{dim} in [{entities_str}]"

    chart_config = {
        'chart_type': 'grouped_bar',
        'x_col': column_map.get('dimensions', [''])[0],
        'y_cols': column_map.get('metrics', [])[:2],
        'color_col': None,
        'filter_expr': filter_expr,
        'title': subject,
        'sort_by': None,
        'top_n': 10,
    }

    df = _load_dataframe(project)
    chart_path = build_chart(chart_config, df) if df is not None else ''

    new_slide = {
        'slide_index': len(slides),
        'slide_type': 'comparison',
        'title': subject,
        'subtitle': f'Filter: {filter_expr}' if filter_expr else '',
        'narrative': f'Filtered view based on: {subject}',
        'chart_png': chart_path,
        'bullet_points': [],
        'speaker_notes': '',
        'insight_ids': [],
        'chart_config': chart_config,
    }

    return {
        'response_text': f'New filtered chart slide added for: {subject}',
        'updated_slide_index': len(slides),
        'slide_data': new_slide,
        'is_new_slide': True,
    }


def _get_objectives_dict(project) -> dict:
    try:
        obj = project.objectives
        return {
            'presentation_title': obj.presentation_title,
            'audience': obj.audience,
            'tone': obj.tone,
            'primary_objectives': obj.primary_objectives,
            'key_metrics': obj.key_metrics,
            'comparison_dimensions': obj.comparison_dimensions,
        }
    except Exception:
        return {}


def _load_dataframe(project) -> pd.DataFrame | None:
    try:
        profile = project.data_file.profile
        sample = profile.get('sample_rows', [])
        if sample:
            return pd.DataFrame(sample)
        return None
    except Exception:
        return None
