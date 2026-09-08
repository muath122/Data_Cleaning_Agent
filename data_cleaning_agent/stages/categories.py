"""Normalize explicitly selected scalar category values in small batches."""

import re
from typing import get_args

import pandas as pd

from ..contracts import Category, CategoryReport, StageResult
from ..model import LocalModel, ModelError
from ..privacy import PreparedData


def column_position(df, column):
    matches = [i for i, name in enumerate(df.columns) if name == column]
    if len(matches) != 1:
        raise ValueError("Target column must exist exactly once; select a unique source column")
    return matches[0]


def run_categories(prepared: PreparedData, column: str, category: str, model=None) -> StageResult:
    if not isinstance(prepared, PreparedData):
        raise TypeError("Category inference requires PreparedData")
    if category not in get_args(Category):
        raise ValueError("Unsupported category")
    df = prepared.dataframe()
    position = column_position(df, column)
    result = StageResult(df.copy(deep=True), "categories")
    eligible = []
    for row, value in enumerate(df.iloc[:, position]):
        if pd.isna(value) or (isinstance(value, str) and not value.strip()):
            continue
        # Do not guess token boundaries or force list-valued answers into scalar mappings.
        if not isinstance(value, str) or re.search(r"[,،;؛\n/|]", value):
            result.issues.append(
                {"row_index": row, "column_index": position, "rule": "unsupported_scalar_value"}
            )
        elif value not in eligible:
            eligible.append(value)
    proposals = []
    client = model or LocalModel()
    for start in range(0, len(eligible), 20):
        batch = eligible[start : start + 20]
        report = client.analyze(
            "categories", {"column": column, "category": category, "values": batch}, CategoryReport
        )
        report = CategoryReport.model_validate(report.model_dump())
        returned = [item.original_value for item in report.results]
        if len(returned) != len(batch) or set(returned) != set(batch):
            raise ModelError("Category response must cover each supplied value exactly once")
        if any(item.column != column or item.category != category for item in report.results):
            raise ModelError("Category response changed the requested column or category")
        proposals.extend(report.results)
    mapping = {item.original_value: item for item in proposals}
    # No mutations occur until every batch has validated.
    for row, value in enumerate(df.iloc[:, position]):
        if not isinstance(value, str) or value not in mapping:
            continue
        item = mapping[value]
        if item.status == "needs_review" or item.confidence < 0.70:
            result.issues.append(
                {
                    "row_index": row,
                    "column_index": position,
                    "rule": "uncertain_category",
                    "confidence": item.confidence,
                }
            )
        elif item.canonical_value != value:
            result.dataframe.iat[row, position] = item.canonical_value
            result.changes.append(
                {
                    "row_index": row,
                    "column_index": position,
                    "before": value,
                    "after": item.canonical_value,
                }
            )
    result.details = {
        "input_provenance": prepared.provenance,
        "mappings": [item.model_dump() for item in proposals],
    }
    return result
