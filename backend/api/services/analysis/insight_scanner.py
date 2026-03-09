"""Steps 6a and 6c: Insight Scan and Insight Extraction (parallel LLM calls).

6a: scan_groups_for_drills  — per-group initial observations + drill-down requests
6c: extract_insights_from_groups — per-group ranked business insights from drill-down results
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..gemini_client import generate_structured
from ..templates.pipeline_prompts import insight_scan_prompt, insight_extraction_prompt_v2

logger = logging.getLogger(__name__)

# ── Step 6a schema ──────────────────────────────────────────────────────────

_DRILL_PARAMS_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
}

_DRILL_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "drill_type": {
            "type": "string",
            "enum": ["cross_tab", "trend", "comparison", "correlation", "gap_analysis"],
        },
        "sheets": {"type": "array", "items": {"type": "string"}},
        "params": _DRILL_PARAMS_SCHEMA,
        "rationale": {"type": "string"},
    },
    "required": ["id", "drill_type", "sheets", "params"],
}

_SCAN_SCHEMA = {
    "type": "object",
    "properties": {
        "observations": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 6,
        },
        "drill_requests": {
            "type": "array",
            "items": _DRILL_REQUEST_SCHEMA,
            "maxItems": 8,
        },
    },
    "required": ["observations", "drill_requests"],
}

# ── Step 6c schema ──────────────────────────────────────────────────────────

_INSIGHT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "insight_id": {"type": "string"},
            "group_id": {"type": "string"},
            "title": {"type": "string"},
            "finding": {"type": "string"},
            "magnitude": {"type": "string", "enum": ["high", "medium", "low"]},
            "source_sheets": {"type": "array", "items": {"type": "string"}},
            "supporting_data": {"type": "object", "additionalProperties": True},
            "visualization_type": {
                "type": "string",
                "enum": ["bar_chart", "line_chart", "scatter", "pie_chart",
                         "heatmap", "grouped_bar", "waterfall"],
            },
            "narrative_hook": {"type": "string"},
            "priority": {"type": "integer"},
        },
        "required": ["insight_id", "group_id", "title", "finding",
                     "magnitude", "visualization_type", "priority"],
    },
    "minItems": 1,
    "maxItems": 8,
}


# ── Public API ───────────────────────────────────────────────────────────────

def scan_groups_for_drills(
    groups: list[dict],
    summary_stats: dict,
    classifications: dict,
    analytical_questions: list[str],
) -> dict:
    """Step 6a: Run insight scan for each group in parallel.

    Returns:
        dict {group_id: {observations: [...], drill_requests: [...]}}
    """
    results = {}
    max_workers = min(4, len(groups))

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_group = {
            executor.submit(
                _scan_one_group,
                group,
                summary_stats.get(group['group_id'], {}),
                classifications,
                analytical_questions,
            ): group['group_id']
            for group in groups
        }

        for future in as_completed(future_to_group):
            group_id = future_to_group[future]
            try:
                scan = future.result()
                results[group_id] = scan
                logger.info(
                    "Scan complete for %s: %d observations, %d drill requests",
                    group_id,
                    len(scan.get('observations', [])),
                    len(scan.get('drill_requests', [])),
                )
            except Exception as e:
                logger.error("Insight scan failed for %s: %s", group_id, e)
                results[group_id] = {'observations': [], 'drill_requests': []}

    return results


def extract_insights_from_groups(
    groups: list[dict],
    summary_stats: dict,
    drill_results: dict,
    full_summary: str,
) -> dict:
    """Step 6c: Extract ranked insights for each group in parallel.

    Returns:
        dict {group_id: list[insight_dict]}
    """
    results = {}
    max_workers = min(4, len(groups))

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_group = {
            executor.submit(
                _extract_one_group,
                group,
                summary_stats.get(group['group_id'], {}),
                drill_results.get(group['group_id'], {}),
                full_summary,
            ): group['group_id']
            for group in groups
        }

        for future in as_completed(future_to_group):
            group_id = future_to_group[future]
            try:
                insights = future.result()
                # Ensure group_id is set on each insight
                for ins in insights:
                    ins['group_id'] = group_id
                results[group_id] = insights
                logger.info(
                    "Extracted %d insights for %s",
                    len(insights), group_id,
                )
            except Exception as e:
                logger.error("Insight extraction failed for %s: %s", group_id, e)
                results[group_id] = []

    return results


# ── Worker functions (run in threads) ────────────────────────────────────────

def _scan_one_group(
    group: dict,
    group_stats: dict,
    classifications: dict,
    analytical_questions: list[str],
) -> dict:
    prompt = insight_scan_prompt(group, group_stats, classifications, analytical_questions)
    return generate_structured(
        prompt, _SCAN_SCHEMA, label=f"insight_scan:{group['group_id']}"
    )


def _extract_one_group(
    group: dict,
    group_stats: dict,
    drill_results: dict,
    full_summary: str,
) -> list[dict]:
    prompt = insight_extraction_prompt_v2(group, group_stats, drill_results, full_summary)
    result = generate_structured(
        prompt, _INSIGHT_SCHEMA, label=f"insight_extract:{group['group_id']}"
    )
    # Schema returns an array directly
    if isinstance(result, list):
        return result
    # Fallback if wrapped in an object
    return result.get('insights', result.get('items', []))
