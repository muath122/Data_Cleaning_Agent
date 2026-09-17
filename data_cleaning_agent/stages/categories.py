"""Normalize explicitly selected scalar category values in small batches."""

import os
import re
from typing import get_args

import pandas as pd

from ..contracts import Category, CategoryReport, StageResult
from ..knowledge import canonical_value
from ..model import LocalModel, ModelError
from ..privacy import PreparedData


MULTI_VALUE_CATEGORIES = {"Skills", "Tools", "Programming languages", "Departments"}


def column_position(df, column):
    matches = [i for i, name in enumerate(df.columns) if name == column]
    if len(matches) != 1:
        raise ValueError("Target column must exist exactly once; select a unique source column")
    return matches[0]


def run_categories(
    prepared: PreparedData, column: str, category: str, model=None, *, batch_size: int | None = None
) -> StageResult:
    if not isinstance(prepared, PreparedData):
        raise TypeError("Category inference requires PreparedData")
    if category not in get_args(Category):
        raise ValueError("Unsupported category")
    df = prepared.dataframe()
    position = column_position(df, column)
    result = StageResult(df.copy(deep=True), "categories")
    batch_size = batch_size or int(os.getenv("QWEN_CATEGORY_BATCH_SIZE", "20"))
    if not 1 <= batch_size <= 50:
        raise ValueError("Category batch size must be between 1 and 50")
    eligible = []
    known = {}
    multi_values = {}
    for row, value in enumerate(df.iloc[:, position]):
        if pd.isna(value) or (isinstance(value, str) and not value.strip()):
            continue
        canonical = canonical_value(value, category)
        if canonical:
            known[value] = canonical
            continue
        separators = r"[,،;؛\n|/]" if category == "Programming languages" else r"[,،;؛\n|]"
        if (
            category in MULTI_VALUE_CATEGORIES
            and isinstance(value, str)
            and re.search(separators, value)
        ):
            parts = [
                part.strip() for part in re.split(rf"\s*{separators}\s*", value) if part.strip()
            ]
            unknown_prose = category == "Programming languages" and any(
                canonical_value(part, category) is None and len(part.split()) > 4
                for part in parts
            )
            if len(parts) > 1 and not unknown_prose:
                multi_values[value] = parts
                for part in parts:
                    if canonical := canonical_value(part, category):
                        known[part] = canonical
                    elif part not in eligible:
                        eligible.append(part)
                continue
        # Slash-delimited values can be one compound term (for example UI/UX).
        if not isinstance(value, str) or "/" in value:
            result.issues.append(
                {"row_index": row, "column_index": position, "rule": "unsupported_scalar_value"}
            )
        elif value not in eligible:
            eligible.append(value)
    proposals = []
    client = (model or LocalModel()) if eligible else None

    def request(batch):
        report = None
        for _attempt in range(2):
            try:
                report = client.analyze(
                    "categories",
                    {"column": column, "category": category, "values": batch},
                    CategoryReport,
                )
                break
            except ModelError:
                continue
        return report

    def accept(batch, report):
        returned = set()
        if report is None:
            return returned
        report = CategoryReport.model_validate(report.model_dump())
        for item in report.results:
            if item.original_value not in batch or item.original_value in returned:
                continue
            item.column = column
            item.category = category
            returned.add(item.original_value)
            proposals.append(item)
        return returned

    for start in range(0, len(eligible), batch_size):
        batch = eligible[start : start + batch_size]
        returned = accept(batch, request(batch))
        missing_values = [value for value in batch if value not in returned]
        recovered = accept(missing_values, request(missing_values)) if missing_values else set()
        for missing in missing_values:
            if missing not in recovered:
                row_indices = [
                    row for row, value in enumerate(df.iloc[:, position]) if value == missing
                ]
                result.issues.append(
                    {
                        "column_index": position,
                        "rule": "missing_category_mapping",
                        "count": len(row_indices),
                        "row_indices": row_indices,
                    }
                )
    mapping = {item.original_value: item for item in proposals}
    # No mutations occur until every batch has validated.
    for row, value in enumerate(df.iloc[:, position]):
        if not isinstance(value, str):
            continue
        if value in multi_values:
            resolved = []
            unresolved = 0
            for part in multi_values[value]:
                if part in known:
                    resolved.append(known[part])
                    continue
                item = mapping.get(part)
                if item and item.status != "needs_review" and item.confidence >= 0.70:
                    resolved.append(
                        canonical_value(item.canonical_value, category) or item.canonical_value
                    )
                else:
                    resolved.append(part)
                    unresolved += 1
            proposed = "; ".join(dict.fromkeys(resolved))
            if proposed != value:
                result.dataframe.iat[row, position] = proposed
                result.changes.append(
                    {
                        "row_index": row,
                        "column_index": position,
                        "before": value,
                        "after": proposed,
                        "source": "multi_value_normalization",
                    }
                )
            if unresolved:
                result.issues.append(
                    {
                        "row_index": row,
                        "column_index": position,
                        "rule": "multi_value_part_needs_review",
                        "count": unresolved,
                    }
                )
            continue
        if value in known:
            if known[value] != value:
                result.dataframe.iat[row, position] = known[value]
                result.changes.append(
                    {
                        "row_index": row,
                        "column_index": position,
                        "before": value,
                        "after": known[value],
                        "source": "knowledge_base",
                    }
                )
            continue
        if value not in mapping:
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
        else:
            # A model may return another alias; enforce the reviewed canonical form
            # at the final application boundary.
            proposed = canonical_value(item.canonical_value, category) or item.canonical_value
            if proposed == value:
                continue
            result.dataframe.iat[row, position] = proposed
            result.changes.append(
                {
                    "row_index": row,
                    "column_index": position,
                    "before": value,
                    "after": proposed,
                    "source": "model_and_knowledge_base"
                    if proposed != item.canonical_value
                    else "model",
                }
            )
    result.details = {
        "input_provenance": prepared.provenance,
        "knowledge_base_matches": len(known),
        "multi_value_inputs": len(multi_values),
        "batch_size": batch_size,
        "mappings": [item.model_dump() for item in proposals],
    }
    return result
