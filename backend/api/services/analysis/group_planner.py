"""Step 4: Sheet Grouping (single LLM call).

Groups sheets into 2-3 analytical groups based on classifications, join graph,
and the analytical questions from BriefDecomposition.
"""
import logging

from ..gemini_client import generate_structured
from ..templates.pipeline_prompts import group_planning_prompt

logger = logging.getLogger(__name__)

_GROUP_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "group_id": {"type": "string"},
            "sheets": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "join_keys": {
                "type": "object",
                "description": "Map of sheet_name -> join column name for keys used in this group",
                "additionalProperties": {"type": "string"},
            },
            "analytical_framing": {"type": "string"},
            "orphan_handling": {
                "type": "string",
                "enum": ["include_standalone", "exclude"],
            },
        },
        "required": ["group_id", "sheets", "analytical_framing"],
    },
    "minItems": 1,
    "maxItems": 4,
}


def plan_groups(
    classifications: dict,
    join_graph: dict,
    analytical_questions: list[str],
) -> list[dict]:
    """Group sheets into analytical clusters.

    Args:
        classifications: Step 2 output — {sheet_name: {column_roles, irrelevant_sheet, summary}}
        join_graph: Step 3 output — {fk_edges, join_paths, orphan_sheets}
        analytical_questions: From BriefDecomposition

    Returns:
        list of group dicts with keys: group_id, sheets, join_keys, analytical_framing
    """
    # Single-sheet case: skip LLM, return one group
    relevant_sheets = [
        s for s, cls in classifications.items()
        if not cls.get('irrelevant_sheet', False)
    ]
    if len(relevant_sheets) == 1:
        logger.info("Single sheet — creating one group without LLM call")
        return [{
            'group_id': 'group_0',
            'sheets': relevant_sheets,
            'join_keys': {},
            'analytical_framing': 'Primary analysis sheet',
        }]

    prompt = group_planning_prompt(classifications, join_graph, analytical_questions)
    groups = generate_structured(prompt, _GROUP_SCHEMA, label="group_planning")

    # Ensure group_ids are normalised
    for i, group in enumerate(groups):
        if not group.get('group_id'):
            group['group_id'] = f'group_{i}'
        group.setdefault('join_keys', {})
        group.setdefault('analytical_framing', '')

    logger.info("Planned %d groups: %s", len(groups), [g['group_id'] for g in groups])
    return groups
