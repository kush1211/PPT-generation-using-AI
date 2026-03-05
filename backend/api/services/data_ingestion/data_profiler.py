import pandas as pd
import numpy as np


def _make_serializable(obj):
    """Recursively convert all non-JSON-serializable types to plain Python."""
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (v != v or v == float('inf') or v == float('-inf')) else v
    if isinstance(obj, np.ndarray):
        return [_make_serializable(i) for i in obj.tolist()]
    if isinstance(obj, float):
        return None if (obj != obj or obj == float('inf') or obj == float('-inf')) else obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def profile_dataframe(df: pd.DataFrame, column_map: dict) -> dict:
    """Generate a statistical profile of the DataFrame."""
    metrics = column_map.get('metrics', [])
    dimensions = column_map.get('dimensions', [])
    dates = column_map.get('dates', [])

    # Basic stats for metric columns
    column_summary = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            column_summary[col] = {
                'min': _safe_val(df[col].min()),
                'max': _safe_val(df[col].max()),
                'mean': _safe_val(df[col].mean()),
                'median': _safe_val(df[col].median()),
                'std': _safe_val(df[col].std()),
                'null_count': int(df[col].isna().sum()),
                'unique_count': int(df[col].nunique()),
            }
        else:
            column_summary[col] = {
                'null_count': int(df[col].isna().sum()),
                'unique_count': int(df[col].nunique()),
                'top_values': df[col].value_counts().head(5).index.tolist(),
            }

    # Top N values per dimension cross metric
    top_n_per_dimension = {}
    for dim in dimensions[:3]:  # limit to top 3 dimensions
        top_n_per_dimension[dim] = {}
        for metric in metrics[:4]:  # limit to top 4 metrics
            try:
                grouped = df.groupby(dim)[metric].mean().sort_values(ascending=False)
                top_n_per_dimension[dim][metric] = {
                    str(k): round(float(v), 2)
                    for k, v in grouped.head(5).items()
                }
            except Exception:
                pass

    # Correlations between metric pairs
    correlations = {}
    if len(metrics) >= 2:
        corr_matrix = df[metrics].corr()
        for i, m1 in enumerate(metrics):
            for m2 in metrics[i+1:]:
                try:
                    val = corr_matrix.loc[m1, m2]
                    if abs(val) >= 0.5:
                        correlations[f"{m1} vs {m2}"] = round(float(val), 3)
                except Exception:
                    pass

    # Trend detection for date columns
    trends = {}
    for date_col in dates[:1]:
        for metric in metrics[:3]:
            try:
                trend_data = df.groupby(date_col)[metric].mean()
                if len(trend_data) >= 2:
                    direction = 'increasing' if trend_data.iloc[-1] > trend_data.iloc[0] else 'decreasing'
                    trends[f"{metric} over {date_col}"] = {
                        'direction': direction,
                        'start': round(float(trend_data.iloc[0]), 2),
                        'end': round(float(trend_data.iloc[-1]), 2),
                    }
            except Exception:
                pass

    # Build condensed text representation for Gemini prompts
    condensed_repr = _build_condensed_repr(df, column_map, column_summary, top_n_per_dimension, trends)

    result = {
        'shape': list(df.shape),
        'columns': df.columns.tolist(),
        'column_map': column_map,
        'column_summary': column_summary,
        'top_n_per_dimension': top_n_per_dimension,
        'correlations': correlations,
        'trends': trends,
        'condensed_repr': condensed_repr,
        'sample_rows': df.head(5).to_dict(orient='records'),
    }
    return _make_serializable(result)


def _build_condensed_repr(df, column_map, column_summary, top_n, trends) -> str:
    lines = []
    lines.append(f"Dataset: {df.shape[0]} rows × {df.shape[1]} columns")
    lines.append(f"Metrics: {', '.join(column_map.get('metrics', []))}")
    lines.append(f"Dimensions: {', '.join(column_map.get('dimensions', []))}")
    if column_map.get('dates'):
        lines.append(f"Time columns: {', '.join(column_map['dates'])}")

    lines.append("\nMetric ranges:")
    for col in column_map.get('metrics', [])[:6]:
        s = column_summary.get(col, {})
        if 'min' in s:
            lines.append(f"  {col}: min={s['min']}, max={s['max']}, mean={s['mean']:.2f}" if isinstance(s.get('mean'), float) else f"  {col}: min={s['min']}, max={s['max']}")

    if top_n:
        lines.append("\nTop values per category:")
        for dim, metrics in list(top_n.items())[:2]:
            for metric, vals in list(metrics.items())[:2]:
                top_str = ', '.join(f"{k}={v}" for k, v in list(vals.items())[:3])
                lines.append(f"  {dim} by {metric}: {top_str}")

    if trends:
        lines.append("\nTrends:")
        for key, t in list(trends.items())[:3]:
            lines.append(f"  {key}: {t['direction']} ({t['start']} → {t['end']})")

    return '\n'.join(lines)


def _safe_val(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    return val


def dataframe_to_serializable(df: pd.DataFrame) -> dict:
    """Convert DataFrame to JSON-serializable dict for storage in JSONField."""
    return {
        'columns': df.columns.tolist(),
        'data': df.where(pd.notnull(df), None).values.tolist(),
        'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
    }


def dataframe_from_serializable(data: dict) -> pd.DataFrame:
    """Restore DataFrame from JSONField dict."""
    return pd.DataFrame(data['data'], columns=data['columns'])
