"""Read-only final checks; this stage never repairs or removes records."""

import re

import pandas as pd

from ..contracts import StageResult
from ..structured.normalizers import infer_supported_role


def run_validation(df: pd.DataFrame) -> StageResult:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Validation requires a dataframe")
    result = StageResult(df.copy(deep=True), "validation")
    blank = df.apply(lambda col: col.map(lambda value: pd.isna(value) or not str(value).strip()))
    duplicate_rows = df.astype(str).duplicated(keep=False)
    for row in df.index[duplicate_rows]:
        result.issues.append({"row_index": int(row), "rule": "duplicate_row"})
    for col, name in enumerate(df.columns):
        missing = int(blank.iloc[:, col].sum())
        if missing:
            result.issues.append(
                {
                    "column_index": col,
                    "rule": "missing_values",
                    "count": missing,
                    "applicability": "unknown",
                }
            )
        role = infer_supported_role(name)
        values = df.iloc[:, col]
        if role == "email":
            invalid = values.map(
                lambda v: (
                    bool(str(v).strip())
                    and not bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(v).strip()))
                )
            )
        elif role == "phone":
            invalid = values.map(
                lambda v: (
                    bool(str(v).strip()) and not bool(re.fullmatch(r"\+9665\d{8}", str(v).strip()))
                )
            )
        else:
            continue
        for row in df.index[invalid]:
            result.issues.append(
                {
                    "row_index": int(row),
                    "column_index": col,
                    "role": role,
                    "rule": f"invalid_{role}",
                }
            )
    result.details = {
        "duplicate_rows": int(duplicate_rows.sum()),
        "missing_cells": int(blank.to_numpy().sum()),
        "read_only": True,
    }
    return result
