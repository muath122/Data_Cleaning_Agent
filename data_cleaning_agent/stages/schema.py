"""Schema proposals are applied by source position, never by model return order."""

import re

import pandas as pd

from ..contracts import ColumnMapping, SchemaReport, StageResult
from ..model import LocalModel, ModelError
from ..privacy import PreparedData


def build_schema_context(df: pd.DataFrame, sample_size=5, max_sample_chars=120) -> list[dict]:
    if sample_size < 1 or max_sample_chars < 1:
        raise ValueError("Sample limits must be positive")
    context = []
    for index, name in enumerate(df.columns):
        column = df.iloc[:, index]
        values = [
            str(value).strip() for value in column if not pd.isna(value) and str(value).strip()
        ]
        unique = list(dict.fromkeys(values))
        context.append(
            {
                "column_index": index,
                "column_name": str(name),
                "pandas_dtype": str(column.dtype),
                "non_null_count": len(values),
                "unique_count": len(unique),
                "sample_values": [
                    v[:max_sample_chars] + ("..." if len(v) > max_sample_chars else "")
                    for v in unique[:sample_size]
                ],
                "is_empty": not values,
            }
        )
    return context


def apply_schema(df: pd.DataFrame, report: SchemaReport) -> StageResult:
    report = SchemaReport.model_validate(report.model_dump())
    indices = [column.column_index for column in report.columns]
    if sorted(indices) != list(range(len(df.columns))):
        raise ModelError("Schema response must cover every column index exactly once")
    context = build_schema_context(df)
    result = StageResult(df.copy(deep=True), "schema")
    names = list(df.columns)
    for column in report.columns:
        i = column.column_index
        if column.original_name != str(df.columns[i]):
            raise ModelError("Schema response changed a source column name")
        if context[i]["is_empty"]:
            column.canonical_name = None
            column.column_type = "empty"
            column.confidence = 1.0
        elif column.canonical_name is None or column.column_type == "empty":
            raise ModelError("Nonempty column has an empty schema mapping")
        elif column.confidence < 0.70:
            result.issues.append(
                {"column_index": i, "rule": "uncertain_schema", "confidence": column.confidence}
            )
        else:
            names[i] = column.canonical_name
        if names[i] != df.columns[i]:
            result.changes.append(
                {"column_index": i, "before": str(df.columns[i]), "after": names[i]}
            )
    if len(names) != len(set(names)):
        counts = {}
        for index, name in enumerate(names):
            counts[name] = counts.get(name, 0) + 1
            if counts[name] > 1:
                names[index] = f"{name}_{counts[name]}"
                result.issues.append({"column_index": index, "rule": "duplicate_canonical_name"})
    result.dataframe.columns = names
    result.details = report.model_dump()
    return result


def _fallback_column(item):
    name = re.sub(r"[^a-z0-9]+", "_", item["column_name"].casefold()).strip("_")
    if not name or not name[0].isalpha():
        name = f"column_{item['column_index'] + 1}"
    return ColumnMapping(
        **{
            "column_index": item["column_index"],
            "original_name": item["column_name"],
            "canonical_name": name or f"column_{item['column_index'] + 1}",
            "column_type": "other",
            "confidence": 0.0,
        }
    )


def run_schema(prepared: PreparedData, model=None, *, batch_size=12) -> StageResult:
    if not isinstance(prepared, PreparedData):
        raise TypeError("Schema inference requires PreparedData, not a raw dataframe")
    df = prepared.dataframe()
    if batch_size < 1:
        raise ValueError("Schema batch size must be positive")
    context = build_schema_context(df)
    client = model or LocalModel()
    mappings, batch_issues = [], []
    for start in range(0, len(context), batch_size):
        batch = context[start : start + batch_size]
        expected = {item["column_index"]: item for item in batch}
        try:
            response = client.analyze("schema", batch, SchemaReport)
            returned = {}
            for column in response.columns:
                if column.column_index in expected and column.column_index not in returned:
                    column.original_name = expected[column.column_index]["column_name"]
                    returned[column.column_index] = column
            for index, item in expected.items():
                if index in returned:
                    mappings.append(returned[index])
                else:
                    mappings.append(_fallback_column(item))
                    batch_issues.append({"column_index": index, "rule": "missing_schema_mapping"})
        except ModelError as exc:
            mappings.extend(_fallback_column(item) for item in batch)
            batch_issues.append(
                {
                    "column_indices": list(expected),
                    "rule": "schema_batch_failed",
                    "message": str(exc),
                }
            )
    seen = {}
    for column in sorted(mappings, key=lambda item: item.column_index):
        if not column.canonical_name:
            continue
        base = column.canonical_name
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            column.canonical_name = f"{base}_{seen[base]}"
    report = SchemaReport(columns=mappings)
    result = apply_schema(df, report)
    result.issues.extend(batch_issues)
    result.details["input_provenance"] = prepared.provenance
    return result
