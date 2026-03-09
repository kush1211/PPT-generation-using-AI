"""Step 1: Multi-sheet metadata extraction.

Loads all sheets from Excel workbooks (or single sheet from CSV) and extracts
structured per-sheet metadata for use in classification and relationship discovery.
"""
import pandas as pd
import numpy as np
from pathlib import Path

from .csv_excel_loader import _sanitize, _find_header_row


def load_all_sheets(file_path: str) -> dict[str, pd.DataFrame]:
    """Load all sheets from an Excel file, or single sheet from CSV.

    Returns:
        dict mapping sheet_name -> sanitized DataFrame
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == '.csv':
        try:
            raw = pd.read_csv(file_path, header=None, nrows=20)
            header_row = _find_header_row(raw)
        except Exception:
            header_row = 0
        df = pd.read_csv(file_path, header=header_row)
        df = _sanitize(df)
        return {'Sheet1': df}

    elif ext in ('.xlsx', '.xls'):
        sheets = {}
        try:
            xf = pd.ExcelFile(file_path)
        except Exception as e:
            raise ValueError(f"Cannot open Excel file: {e}")

        for sheet_name in xf.sheet_names:
            try:
                raw = xf.parse(sheet_name, header=None, nrows=20)
                header_row = _find_header_row(raw)
                df = xf.parse(sheet_name, header=header_row)
                df = _sanitize(df)
                if df.empty or len(df.columns) == 0:
                    continue
                sheets[sheet_name] = df
            except Exception:
                continue  # skip unparseable sheets

        if not sheets:
            raise ValueError("No parseable sheets found in Excel file.")
        return sheets

    else:
        raise ValueError(f"Unsupported file type: {ext}")


def extract_sheet_metadata(sheet_dfs: dict[str, pd.DataFrame]) -> dict:
    """Extract structured metadata per sheet for LLM classification.

    Returns:
        dict mapping sheet_name -> metadata dict with keys:
            columns, sample_top, sample_mid, sample_bot,
            row_count, unique_counts, null_pct, inferred_dtypes
    """
    metadata = {}
    for sheet_name, df in sheet_dfs.items():
        n = len(df)
        mid_idx = n // 2

        sample_top = _rows_to_records(df.head(3))
        sample_mid = _rows_to_records(df.iloc[max(0, mid_idx - 1): mid_idx + 2])
        sample_bot = _rows_to_records(df.tail(3))

        unique_counts = {}
        null_pct = {}
        inferred_dtypes = {}

        for col in df.columns:
            series = df[col]
            unique_counts[col] = int(series.nunique())
            null_pct[col] = round(float(series.isna().mean()) * 100, 1)
            inferred_dtypes[col] = _infer_dtype(series)

        metadata[sheet_name] = {
            'columns': list(df.columns),
            'sample_top': sample_top,
            'sample_mid': sample_mid,
            'sample_bot': sample_bot,
            'row_count': n,
            'unique_counts': unique_counts,
            'null_pct': null_pct,
            'inferred_dtypes': inferred_dtypes,
        }

    return metadata


def _rows_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a small DataFrame slice to a list of plain dicts (JSON-serializable)."""
    records = []
    for _, row in df.iterrows():
        rec = {}
        for col, val in row.items():
            if pd.isna(val) if not isinstance(val, (list, dict)) else False:
                rec[col] = None
            elif isinstance(val, (np.integer,)):
                rec[col] = int(val)
            elif isinstance(val, (np.floating,)):
                rec[col] = round(float(val), 4)
            elif isinstance(val, np.bool_):
                rec[col] = bool(val)
            else:
                rec[col] = str(val) if not isinstance(val, (int, float, bool, str, type(None))) else val
        records.append(rec)
    return records


def _infer_dtype(series: pd.Series) -> str:
    """Classify a column's data type as one of: numeric, date, text, boolean, mixed."""
    if pd.api.types.is_bool_dtype(series):
        return 'boolean'
    if pd.api.types.is_numeric_dtype(series):
        return 'numeric'
    if pd.api.types.is_datetime64_any_dtype(series):
        return 'date'
    # Try parsing as date
    sample = series.dropna().head(5).astype(str)
    try:
        pd.to_datetime(sample, infer_datetime_format=True, errors='raise')
        return 'date'
    except Exception:
        pass
    return 'text'


def get_primary_sheet(sheet_dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return the largest sheet by row count (used for backward compat with single-sheet code)."""
    return max(sheet_dfs.values(), key=lambda df: len(df))
