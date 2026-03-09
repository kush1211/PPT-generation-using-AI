"""Step 5: Summary Profiling (pure Python).

Intentionally shallow — provides quick stats per group without deep breakdowns.
Results feed into Step 6a (Insight Scan).
"""
import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def profile_groups(
    sheet_dfs: dict[str, pd.DataFrame],
    groups: list[dict],
    classifications: dict,
) -> dict:
    """Produce shallow stats for each group.

    Args:
        sheet_dfs: {sheet_name: DataFrame}
        groups: Step 4 output — list of group dicts
        classifications: Step 2 output — {sheet_name: {column_roles, ...}}

    Returns:
        dict {group_id: {metrics: {...}, dimensions: {...}, joins: {...}}}
    """
    summary = {}
    for group in groups:
        group_id = group['group_id']
        group_sheets = group.get('sheets', [])
        join_keys = group.get('join_keys', {})

        metrics_stats: dict[str, Any] = {}
        dimension_stats: dict[str, Any] = {}
        join_stats: dict[str, Any] = {}

        for sheet_name in group_sheets:
            df = sheet_dfs.get(sheet_name)
            if df is None or df.empty:
                continue
            cls = classifications.get(sheet_name, {})
            roles = cls.get('column_roles', {})

            metric_cols = [c for c, r in roles.items() if r == 'metric' and c in df.columns]
            dim_cols = [c for c, r in roles.items() if r == 'dimension' and c in df.columns]
            date_cols = [c for c, r in roles.items() if r == 'date' and c in df.columns]

            for col in metric_cols:
                series = df[col].dropna()
                if series.empty:
                    continue
                key = f"{sheet_name}.{col}"
                metrics_stats[key] = {
                    'sheet': sheet_name,
                    'column': col,
                    'mean': _safe_float(series.mean()),
                    'median': _safe_float(series.median()),
                    'min': _safe_float(series.min()),
                    'max': _safe_float(series.max()),
                    'std': _safe_float(series.std()),
                    'trend_direction': _trend_direction(series),
                    'outlier_count': int(_count_outliers(series)),
                    'row_count': int(len(series)),
                }

            for col in dim_cols:
                series = df[col].dropna().astype(str)
                if series.empty:
                    continue
                key = f"{sheet_name}.{col}"
                vc = series.value_counts()
                top3 = vc.head(3).to_dict()
                concentration = float(vc.head(3).sum() / max(len(series), 1))
                dimension_stats[key] = {
                    'sheet': sheet_name,
                    'column': col,
                    'cardinality': int(series.nunique()),
                    'top_3': top3,
                    'concentration_ratio': round(concentration, 3),
                }

            # Cross-sheet join coverage if join_keys available
            if len(group_sheets) > 1 and join_keys:
                for sa, col_a in join_keys.items():
                    if sa != sheet_name:
                        continue
                    for sb in group_sheets:
                        if sb == sa:
                            continue
                        col_b = join_keys.get(sb)
                        if not col_b:
                            continue
                        df_b = sheet_dfs.get(sb)
                        if df_b is None or col_a not in df.columns or col_b not in df_b.columns:
                            continue
                        set_a = set(df[col_a].dropna().astype(str))
                        set_b = set(df_b[col_b].dropna().astype(str))
                        if set_a and set_b:
                            coverage = len(set_a & set_b) / min(len(set_a), len(set_b))
                            jkey = f"{sa}→{sb}"
                            join_stats[jkey] = {
                                'from_sheet': sa,
                                'to_sheet': sb,
                                'join_col_a': col_a,
                                'join_col_b': col_b,
                                'join_coverage_pct': round(coverage * 100, 1),
                            }

        summary[group_id] = {
            'metrics': metrics_stats,
            'dimensions': dimension_stats,
            'joins': join_stats,
        }
        logger.info(
            "Group %s: %d metric cols, %d dimension cols profiled",
            group_id, len(metrics_stats), len(dimension_stats),
        )

    return summary


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return round(f, 4) if not (f != f) else None  # NaN check
    except (TypeError, ValueError):
        return None


def _trend_direction(series: pd.Series) -> str:
    """Quick linear trend via first/last thirds comparison."""
    n = len(series)
    if n < 3:
        return 'flat'
    third = max(1, n // 3)
    first_mean = series.iloc[:third].mean()
    last_mean = series.iloc[-third:].mean()
    if abs(first_mean) < 1e-10:
        return 'flat'
    change = (last_mean - first_mean) / abs(first_mean)
    if change > 0.05:
        return 'up'
    elif change < -0.05:
        return 'down'
    return 'flat'


def _count_outliers(series: pd.Series) -> int:
    """Count values beyond 3 standard deviations from the mean."""
    mean = series.mean()
    std = series.std()
    if std == 0 or np.isnan(std):
        return 0
    return int(((series - mean).abs() > 3 * std).sum())
