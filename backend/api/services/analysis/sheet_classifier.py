"""Step 2: Sheet Classification (parallel LLM calls).

Classifies every column in every sheet with a semantic role:
metric / dimension / date / id / foreign_key_candidate / text / irrelevant.
Runs N LLM calls in parallel via ThreadPoolExecutor.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..gemini_client import generate_structured
from ..templates.pipeline_prompts import sheet_classification_prompt

logger = logging.getLogger(__name__)

_CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "column_roles": {
            "type": "object",
            "description": "Map of column_name -> role string",
            "additionalProperties": {
                "type": "string",
                "enum": ["metric", "dimension", "date", "id",
                         "foreign_key_candidate", "text", "irrelevant"],
            },
        },
        "irrelevant_sheet": {
            "type": "boolean",
            "description": "True if the entire sheet has no analytical value",
        },
        "summary": {
            "type": "string",
            "description": "One-line description of what this sheet represents",
        },
        "confidence_notes": {
            "type": "string",
            "description": "Notes on columns that were hard to classify",
        },
    },
    "required": ["column_roles", "irrelevant_sheet", "summary"],
}


def classify_sheets(sheet_metadata: dict, domain_context: str) -> dict:
    """Classify all sheets in parallel.

    Args:
        sheet_metadata: Output of multi_sheet_loader.extract_sheet_metadata()
        domain_context: domain_context field from BriefDecomposition

    Returns:
        dict mapping sheet_name -> classification result
    """
    results = {}
    max_workers = min(6, len(sheet_metadata))

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_sheet = {
            executor.submit(_classify_one_sheet, sheet_name, meta, domain_context): sheet_name
            for sheet_name, meta in sheet_metadata.items()
        }

        for future in as_completed(future_to_sheet):
            sheet_name = future_to_sheet[future]
            try:
                classification = future.result()
                results[sheet_name] = classification
                logger.info(
                    "Classified sheet %r: %d roles, irrelevant=%s",
                    sheet_name,
                    len(classification.get('column_roles', {})),
                    classification.get('irrelevant_sheet', False),
                )
            except Exception as e:
                logger.error("Classification failed for sheet %r: %s", sheet_name, e)
                # Provide a safe fallback — treat all columns as unknown
                results[sheet_name] = {
                    'column_roles': {
                        col: 'text'
                        for col in sheet_metadata[sheet_name].get('columns', [])
                    },
                    'irrelevant_sheet': False,
                    'summary': f"Sheet {sheet_name} (classification failed)",
                    'confidence_notes': str(e),
                }

    return results


def _classify_one_sheet(sheet_name: str, metadata: dict, domain_context: str) -> dict:
    """Classify a single sheet — runs in a worker thread."""
    prompt = sheet_classification_prompt(sheet_name, metadata, domain_context)
    result = generate_structured(prompt, _CLASSIFICATION_SCHEMA,
                                  label=f"classify_sheet:{sheet_name}")

    # Validate all columns are classified
    expected_cols = set(metadata.get('columns', []))
    classified_cols = set(result.get('column_roles', {}).keys())
    missing = expected_cols - classified_cols
    if missing:
        for col in missing:
            result['column_roles'][col] = 'text'
        logger.warning("Sheet %r: LLM missed columns %s — defaulting to 'text'", sheet_name, missing)

    return result
