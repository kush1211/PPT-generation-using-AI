"""Step 6b: Targeted Profiling (pure Python).

Executes typed drill-down requests from Step 6a.
Each drill_type maps to a pre-built function. Max 8 per group (~24 total).
Results are JSON-serializable dicts tagged with the request ID.
"""
import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_MAX_DRILLS_PER_GROUP = 8
_TOP_N_DEFAULT = 10


def run_drill_downs(
    sheet_dfs: dict[str, pd.DataFrame],
    drill_requests: list[dict],
    group_sheets: list[str],
) -> dict:
    """Execute typed drill-down requests for one group.

    Args:
        sheet_dfs: All sheet DataFrames (may include sheets outside this group)
        drill_requests: list of drill request dicts from Step 6a
        group_sheets: Sheet names in this group (for scoping)

    Returns:
        dict {drill_id: result_dict}
    """
    results = {}
    group_dfs = {s: sheet_dfs[s] for s in group_sheets if s in sheet_dfs}

    for req in drill_requests[:_MAX_DRILLS_PER_GROUP]:
        drill_id = req.get('id', f"drill_{len(results)}")
        drill_type = req.get('drill_type', '')
        params = req.get('params', {})
        sheets = req.get('sheets', group_sheets)

        try:
            req_dfs = {s: sheet_dfs[s] for s in sheets if s in sheet_dfs}
            if not req_dfs:
                req_dfs = group_dfs

            if drill_type == 'cross_tab':
                result = _cross_tab(req_dfs, params)
            elif drill_type == 'trend':
                result = _trend(req_dfs, params)
            elif drill_type == 'comparison':
                result = _comparison(req_dfs, params)
            elif drill_type == 'correlation':
                result = _correlation(req_dfs, params)
            elif drill_type == 'gap_analysis':
                result = _gap_analysis(req_dfs, params)
            else:
                result = {'error': f'Unknown drill_type: {drill_type}'}

            results[drill_id] = {'drill_type': drill_type, 'params': params, **result}
            logger.debug("Drill %s (%s): success", drill_id, drill_type)

        except Exception as e:
            logger.warning("Drill %s (%s) failed: %s", drill_id, drill_type, e)
            results[drill_id] = {
                'drill_type': drill_type,
                'params': params,
                'error': str(e),
                'computable': False,
            }

    return results


# ── Drill-down implementations ───────────────────────────────────────────────

def _cross_tab(dfs: dict[str, pd.DataFrame], params: dict) -> dict:
    """Group a metric by a dimension and aggregate."""
    df = _get_primary_df(dfs)
    metric_col = _find_col(df, params.get('metric_col', ''))
    group_by_col = _find_col(df, params.get('group_by_col', ''))
    agg_func = params.get('agg_func', 'sum')

    if not metric_col or not group_by_col:
        return {'computable': False, 'error': 'Missing metric_col or group_by_col'}

    grouped = df.groupby(group_by_col)[metric_col].agg(agg_func).sort_values(ascending=False)
    top = grouped.head(_TOP_N_DEFAULT)

    return {
        'computable': True,
        'group_by': group_by_col,
        'metric': metric_col,
        'agg_func': agg_func,
        'data': _series_to_records(top),
        'total': _safe_float(grouped.sum()),
        'top_value': _safe_float(top.iloc[0]) if len(top) else None,
        'top_label': str(top.index[0]) if len(top) else None,
    }


def _trend(dfs: dict[str, pd.DataFrame], params: dict) -> dict:
    """Aggregate a metric over a date column."""
    df = _get_primary_df(dfs)
    metric_col = _find_col(df, params.get('metric_col', ''))
    date_col = _find_col(df, params.get('date_col', ''))
    freq = params.get('freq', 'M')

    if not metric_col or not date_col:
        return {'computable': False, 'error': 'Missing metric_col or date_col'}

    df = df.copy()
    try:
        df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True, errors='coerce')
    except Exception:
        pass

    df = df.dropna(subset=[date_col, metric_col])
    if df.empty:
        return {'computable': False, 'error': 'No data after date parsing'}

    df = df.set_index(date_col).sort_index()
    try:
        series = df[metric_col].resample(freq).sum()
    except Exception:
        series = df[metric_col]

    data = _series_to_records(series)
    if len(data) < 2:
        return {'computable': True, 'data': data, 'trend_direction': 'flat'}

    first_val = data[0]['value']
    last_val = data[-1]['value']
    direction = 'up' if last_val > first_val else ('down' if last_val < first_val else 'flat')
    pct_change = ((last_val - first_val) / abs(first_val) * 100) if first_val else 0

    return {
        'computable': True,
        'metric': metric_col,
        'date_col': date_col,
        'freq': freq,
        'data': data,
        'trend_direction': direction,
        'pct_change': round(pct_change, 1),
    }


def _comparison(dfs: dict[str, pd.DataFrame], params: dict) -> dict:
    """Compare a metric across top N values of a dimension."""
    df = _get_primary_df(dfs)
    metric_col = _find_col(df, params.get('metric_col', ''))
    dim_col = _find_col(df, params.get('dimension_col', ''))
    top_n = int(params.get('top_n', 10))
    agg_func = params.get('agg_func', 'sum')

    if not metric_col or not dim_col:
        return {'computable': False, 'error': 'Missing metric_col or dimension_col'}

    grouped = df.groupby(dim_col)[metric_col].agg(agg_func).sort_values(ascending=False)
    top = grouped.head(top_n)
    bottom = grouped.tail(min(3, len(grouped) - top_n)) if len(grouped) > top_n else pd.Series(dtype=float)

    return {
        'computable': True,
        'metric': metric_col,
        'dimension': dim_col,
        'top_n': top_n,
        'agg_func': agg_func,
        'top': _series_to_records(top),
        'bottom': _series_to_records(bottom),
        'spread': _safe_float(top.iloc[0] - top.iloc[-1]) if len(top) > 1 else None,
        'leader': str(top.index[0]) if len(top) else None,
        'leader_value': _safe_float(top.iloc[0]) if len(top) else None,
    }


def _correlation(dfs: dict[str, pd.DataFrame], params: dict) -> dict:
    """Compute Pearson correlation between two metric columns (possibly across sheets)."""
    metric_a = params.get('metric_col_a', '')
    metric_b = params.get('metric_col_b', '')
    sheet_a_name = params.get('sheet_a', '')
    sheet_b_name = params.get('sheet_b', '')

    df_a = dfs.get(sheet_a_name) if sheet_a_name in dfs else _get_primary_df(dfs)
    df_b = dfs.get(sheet_b_name) if sheet_b_name in dfs else df_a

    col_a = _find_col(df_a, metric_a)
    col_b = _find_col(df_b, metric_b)

    if not col_a or not col_b:
        return {'computable': False, 'error': 'Could not find metric columns'}

    if df_a is df_b:
        series_a = df_a[col_a].dropna()
        series_b = df_b[col_b].dropna()
        min_len = min(len(series_a), len(series_b))
        series_a = series_a.iloc[:min_len]
        series_b = series_b.iloc[:min_len]
    else:
        # If different sheets, align by index length
        series_a = df_a[col_a].dropna().reset_index(drop=True)
        series_b = df_b[col_b].dropna().reset_index(drop=True)
        min_len = min(len(series_a), len(series_b))
        series_a = series_a.iloc[:min_len]
        series_b = series_b.iloc[:min_len]

    if min_len < 3:
        return {'computable': False, 'error': 'Insufficient data for correlation'}

    r = series_a.corr(series_b)
    strength = 'strong' if abs(r) > 0.7 else ('moderate' if abs(r) > 0.4 else 'weak')
    direction = 'positive' if r > 0 else 'negative'

    return {
        'computable': True,
        'metric_a': col_a,
        'metric_b': col_b,
        'pearson_r': round(float(r), 4),
        'strength': strength,
        'direction': direction,
        'sample_size': min_len,
    }


def _gap_analysis(dfs: dict[str, pd.DataFrame], params: dict) -> dict:
    """Find keys present in one sheet but missing from another."""
    key_col_a = params.get('key_col_a', '')
    key_col_b = params.get('key_col_b', '')
    sheet_a_name = params.get('sheet_a', '')
    sheet_b_name = params.get('sheet_b', '')

    df_a = dfs.get(sheet_a_name)
    df_b = dfs.get(sheet_b_name)

    if df_a is None or df_b is None:
        names = list(dfs.keys())
        df_a = dfs.get(names[0]) if len(names) > 0 else None
        df_b = dfs.get(names[1]) if len(names) > 1 else None

    if df_a is None or df_b is None:
        return {'computable': False, 'error': 'Need at least 2 sheets for gap analysis'}

    col_a = _find_col(df_a, key_col_a) or (df_a.columns[0] if len(df_a.columns) else None)
    col_b = _find_col(df_b, key_col_b) or (df_b.columns[0] if len(df_b.columns) else None)

    if not col_a or not col_b:
        return {'computable': False, 'error': 'Could not find key columns'}

    set_a = set(df_a[col_a].dropna().astype(str))
    set_b = set(df_b[col_b].dropna().astype(str))

    only_in_a = set_a - set_b
    only_in_b = set_b - set_a
    in_both = set_a & set_b

    return {
        'computable': True,
        'key_col_a': col_a,
        'key_col_b': col_b,
        'total_a': len(set_a),
        'total_b': len(set_b),
        'in_both': len(in_both),
        'only_in_a_count': len(only_in_a),
        'only_in_b_count': len(only_in_b),
        'only_in_a_sample': list(only_in_a)[:10],
        'only_in_b_sample': list(only_in_b)[:10],
        'overlap_pct': round(len(in_both) / max(len(set_a | set_b), 1) * 100, 1),
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_primary_df(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return the largest DataFrame (by rows) from the group."""
    return max(dfs.values(), key=len)


def _find_col(df: pd.DataFrame, col_name: str) -> str | None:
    """Find a column by exact name, then case-insensitive fuzzy match."""
    if not col_name:
        return None
    if col_name in df.columns:
        return col_name
    col_lower = col_name.lower().replace(' ', '_').replace('-', '_')
    for c in df.columns:
        if c.lower().replace(' ', '_').replace('-', '_') == col_lower:
            return c
    return None


def _series_to_records(series: pd.Series) -> list[dict]:
    """Convert a Series to a list of {label, value} dicts."""
    records = []
    for idx, val in series.items():
        records.append({
            'label': str(idx),
            'value': _safe_float(val),
        })
    return records


def _safe_float(val: Any) -> float | None:
    try:
        f = float(val)
        return round(f, 4) if not np.isnan(f) else None
    except (TypeError, ValueError):
        return None
