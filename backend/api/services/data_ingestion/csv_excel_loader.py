import pandas as pd
import numpy as np
from pathlib import Path


def load_file(file_path: str) -> tuple[pd.DataFrame, dict]:
    """Load CSV or Excel file. Returns (DataFrame, column_type_map)."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == '.csv':
        header_row = _detect_header_row_csv(file_path)
        df = pd.read_csv(file_path, header=header_row)
    elif ext in ('.xlsx', '.xls'):
        header_row = _detect_header_row_excel(file_path)
        df = pd.read_excel(file_path, header=header_row)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    df = _sanitize(df)
    column_map = _infer_column_types(df)
    return df, column_map


def _detect_header_row_excel(file_path: str) -> int:
    """Find the first row where most cells are non-null strings (i.e. real column headers)."""
    try:
        raw = pd.read_excel(file_path, header=None, nrows=20)
        return _find_header_row(raw)
    except Exception:
        return 0


def _detect_header_row_csv(file_path: str) -> int:
    """Same heuristic for CSV files."""
    try:
        raw = pd.read_csv(file_path, header=None, nrows=20)
        return _find_header_row(raw)
    except Exception:
        return 0


def _find_header_row(df_raw: pd.DataFrame) -> int:
    """
    Scan raw rows and return the index of the first row that looks like column headers:
    - At least 50% of cells are non-null
    - At least 50% of those non-null cells are strings
    """
    n_cols = len(df_raw.columns)
    threshold = max(2, n_cols * 0.5)

    for i, row in df_raw.iterrows():
        non_null = row.dropna()
        if len(non_null) >= threshold:
            str_ratio = sum(isinstance(v, str) for v in non_null) / len(non_null)
            if str_ratio >= 0.5:
                return int(i)
    return 0


_SUMMARY_ROW_KEYWORDS = {'total', 'average', 'avg', 'subtotal', 'grand total', 'sum', 'mean'}


def _sanitize(df: pd.DataFrame) -> pd.DataFrame:
    # Drop fully empty rows/columns
    df = df.dropna(how='all').dropna(axis=1, how='all')
    # Strip whitespace from string columns
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].str.strip()
    # Drop summary/total rows (e.g. "TOTAL / AVG" at the bottom of report tables)
    if len(df.columns) > 0:
        first_col = df.iloc[:, 0]
        mask = first_col.astype(str).str.lower().str.strip().apply(
            lambda v: not any(k in v for k in _SUMMARY_ROW_KEYWORDS)
        )
        df = df[mask]
    # Try to parse object columns that look numeric (handles "₹79,999" → strip symbols)
    for col in df.select_dtypes(include='object').columns:
        try:
            cleaned = df[col].str.replace(r'[^\d.\-]', '', regex=True)
            df[col] = pd.to_numeric(cleaned, errors='raise')
        except (ValueError, AttributeError):
            pass
    return df.reset_index(drop=True)


def _infer_column_types(df: pd.DataFrame) -> dict:
    metrics, dimensions, dates = [], [], []

    date_keywords = {'date', 'month', 'year', 'quarter', 'week', 'day', 'period', 'time'}
    id_keywords = {'id', 'code', 'index', 'key', 'no', 'num', 'number'}

    for col in df.columns:
        col_lower = col.lower().replace(' ', '_').replace('-', '_')

        # Check for date columns
        if any(k in col_lower for k in date_keywords):
            dates.append(col)
            continue

        # Skip ID-like columns
        if any(k == col_lower or col_lower.endswith(f'_{k}') for k in id_keywords):
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            # Numeric with high cardinality → metric
            if df[col].nunique() > 10:
                metrics.append(col)
            else:
                # Low cardinality numeric → could be rating/score, treat as metric
                metrics.append(col)
        else:
            dimensions.append(col)

    return {'metrics': metrics, 'dimensions': dimensions, 'dates': dates}
