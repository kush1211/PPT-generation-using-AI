"""Step 3: Relationship Discovery (pure Python).

Deterministically finds FK relationships between sheets using set intersection,
computes cardinality, builds a join graph, and detects orphan sheets.
"""
import logging
from itertools import combinations

import pandas as pd

logger = logging.getLogger(__name__)

# FK detection threshold: at least 70% of values from the smaller set must appear in the larger
_FK_THRESHOLD = 0.7
# Avoid spurious FK matches on very low-cardinality columns (e.g. month numbers 1-12)
_MIN_UNIQUE_FOR_FK = 5


def discover_relationships(
    sheet_dfs: dict[str, pd.DataFrame],
    classifications: dict,
) -> dict:
    """Find FK edges, cardinality, join graph, and orphan sheets.

    Args:
        sheet_dfs: dict of sheet_name -> DataFrame
        classifications: Step 2 output — {sheet_name: {column_roles, ...}}

    Returns:
        dict with keys:
            fk_edges: list of {sheet_a, col_a, sheet_b, col_b, overlap_ratio, cardinality}
            join_paths: adjacency list {sheet: [{to, via_a, via_b, overlap_ratio, cardinality}]}
            orphan_sheets: list[str]
    """
    fk_edges = []
    sheet_names = list(sheet_dfs.keys())

    # Collect candidate FK columns per sheet (id + foreign_key_candidate + high-cardinality dimensions)
    fk_candidates = {}
    for sheet_name, cls in classifications.items():
        roles = cls.get('column_roles', {})
        candidates = [
            col for col, role in roles.items()
            if role in ('id', 'foreign_key_candidate', 'dimension')
        ]
        fk_candidates[sheet_name] = candidates

    # Compare every pair of sheets
    for sheet_a, sheet_b in combinations(sheet_names, 2):
        df_a = sheet_dfs[sheet_a]
        df_b = sheet_dfs[sheet_b]
        cols_a = fk_candidates.get(sheet_a, [])
        cols_b = fk_candidates.get(sheet_b, [])

        for col_a in cols_a:
            if col_a not in df_a.columns:
                continue
            set_a = set(df_a[col_a].dropna().astype(str))
            if len(set_a) < _MIN_UNIQUE_FOR_FK:
                continue

            for col_b in cols_b:
                if col_b not in df_b.columns:
                    continue
                set_b = set(df_b[col_b].dropna().astype(str))
                if len(set_b) < _MIN_UNIQUE_FOR_FK:
                    continue

                overlap_ratio = _set_intersection_ratio(set_a, set_b)
                if overlap_ratio >= _FK_THRESHOLD:
                    cardinality = _compute_cardinality(df_a, col_a, df_b, col_b)
                    edge = {
                        'sheet_a': sheet_a,
                        'col_a': col_a,
                        'sheet_b': sheet_b,
                        'col_b': col_b,
                        'overlap_ratio': round(overlap_ratio, 3),
                        'cardinality': cardinality,
                    }
                    fk_edges.append(edge)
                    logger.debug(
                        "FK: %s.%s <-> %s.%s (overlap=%.2f, %s)",
                        sheet_a, col_a, sheet_b, col_b, overlap_ratio, cardinality,
                    )

    # Deduplicate: keep highest-overlap edge per (sheet_a, sheet_b) pair
    fk_edges = _deduplicate_edges(fk_edges)

    # Build join-path adjacency list
    join_paths = _build_join_graph(fk_edges, sheet_names)

    # Detect orphan sheets (no edges in either direction)
    connected = set()
    for edge in fk_edges:
        connected.add(edge['sheet_a'])
        connected.add(edge['sheet_b'])
    orphan_sheets = [s for s in sheet_names if s not in connected]

    logger.info(
        "Relationship discovery: %d FK edges, %d orphan sheets",
        len(fk_edges), len(orphan_sheets),
    )

    return {
        'fk_edges': fk_edges,
        'join_paths': join_paths,
        'orphan_sheets': orphan_sheets,
    }


def _set_intersection_ratio(set_a: set, set_b: set) -> float:
    """Compute overlap ratio: |A ∩ B| / min(|A|, |B|)."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    return intersection / min(len(set_a), len(set_b))


def _compute_cardinality(df_a: pd.DataFrame, col_a: str,
                          df_b: pd.DataFrame, col_b: str) -> str:
    """Determine 1:1, 1:N, or M:N cardinality between two columns."""
    unique_a = df_a[col_a].nunique()
    unique_b = df_b[col_b].nunique()
    total_a = len(df_a[col_a].dropna())
    total_b = len(df_b[col_b].dropna())

    a_is_unique = unique_a == total_a
    b_is_unique = unique_b == total_b

    if a_is_unique and b_is_unique:
        return '1:1'
    elif a_is_unique and not b_is_unique:
        return '1:N'
    elif not a_is_unique and b_is_unique:
        return 'N:1'
    else:
        return 'M:N'


def _deduplicate_edges(edges: list[dict]) -> list[dict]:
    """Keep only the highest-overlap edge for each (sheet_a, sheet_b) pair."""
    best: dict[tuple, dict] = {}
    for edge in edges:
        key = (edge['sheet_a'], edge['sheet_b'])
        if key not in best or edge['overlap_ratio'] > best[key]['overlap_ratio']:
            best[key] = edge
    return list(best.values())


def _build_join_graph(fk_edges: list[dict], sheet_names: list[str]) -> dict:
    """Build an adjacency list join graph from FK edges."""
    graph: dict[str, list] = {s: [] for s in sheet_names}

    for edge in fk_edges:
        sa, ca = edge['sheet_a'], edge['col_a']
        sb, cb = edge['sheet_b'], edge['col_b']
        overlap = edge['overlap_ratio']
        cardinality = edge['cardinality']

        graph[sa].append({'to': sb, 'via_a': ca, 'via_b': cb,
                           'overlap_ratio': overlap, 'cardinality': cardinality})
        graph[sb].append({'to': sa, 'via_a': cb, 'via_b': ca,
                           'overlap_ratio': overlap, 'cardinality': cardinality})

    return graph
