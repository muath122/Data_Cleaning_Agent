"""End-to-end orchestration for folders containing CSV and Excel form exports."""

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from .contracts import StageResult
from .io import read_table
from .model import LocalModel, ModelError
from .privacy import prepare_private_data, restore_identities
from .stages.categories import run_categories
from .stages.schema import run_schema
from .stages.structured import run_structured
from .stages.text import run_text
from .stages.validation import run_validation

STAGE_STATUS = {
    "schema": "implemented with local-Qwen inference and deterministic fallback",
    "structured": "implemented with deterministic normalization",
    "categories": "implemented with local-Qwen semantic normalization",
    "text": "implemented with meaning-preserving cleanup and missing flags",
    "validation": "implemented as read-only checks",
    "privacy": "implemented as local in-memory masking before model calls",
}

CATEGORY_NAMES = {
    "major": "Major",
    "committee": "Committee",
    "skills": "Skills",
    "tools": "Tools",
    "programming_languages": "Programming languages",
    "role": "Roles",
    "department": "Departments",
}


def _safe_name(path: Path, sheet: str | None) -> str:
    base = re.sub(r"[^\w.-]+", "_", path.stem, flags=re.UNICODE).strip("_")[:70] or "table"
    label = f"{path.name}|{sheet or ''}"
    return f"{base}-{hashlib.sha256(label.encode()).hexdigest()[:10]}"


def discover_tables(path: str | Path):
    source = Path(path)
    files = [source] if source.is_file() else sorted(source.glob("*"))
    for file in files:
        if file.suffix.lower() == ".csv":
            yield file, None
        elif file.suffix.lower() == ".xlsx":
            for sheet in pd.ExcelFile(file, engine="openpyxl").sheet_names:
                yield file, sheet


def _fallback_schema(df: pd.DataFrame, reason: str) -> StageResult:
    result = StageResult(df.copy(deep=True), "schema")
    used = set()
    aliases = {
        "timestamp": "timestamp",
        "email": "email",
        "e mail": "email",
        "phone number": "phone",
        "gender": "gender",
        "university": "university",
        "university id": "university_id",
        "major": "major",
        "academic level": "academic_level",
        "attendance": "attendance",
        "department": "department",
        "role": "role",
    }
    names = []
    for index, original in enumerate(df.columns):
        key = re.sub(r"\s+", " ", str(original).replace("_", " ").strip().casefold())
        canonical = next((value for alias, value in aliases.items() if alias in key), None)
        canonical = canonical or f"column_{index + 1}"
        candidate, suffix = canonical, 2
        while candidate in used:
            candidate = f"{canonical}_{suffix}"
            suffix += 1
        used.add(candidate)
        names.append(candidate)
    result.dataframe.columns = names
    result.issues.append({"rule": "schema_model_fallback", "message": reason})
    result.details = {
        "columns": [
            {
                "column_index": i,
                "original_name": str(old),
                "canonical_name": new,
                "column_type": "other",
                "confidence": 0.0,
            }
            for i, (old, new) in enumerate(zip(df.columns, names))
        ]
    }
    return result


def _schema_raw(df: pd.DataFrame, model) -> StageResult:
    prepared, _vault = prepare_private_data(df)
    try:
        proposal = run_schema(prepared, model=model)
        raw = df.copy(deep=True)
        raw.columns = proposal.dataframe.columns
        raw.attrs.update(df.attrs)
        proposal.dataframe = raw
        return proposal
    except (ModelError, ValueError) as exc:
        return _fallback_schema(df, str(exc))


def run_table(df: pd.DataFrame, *, model=None) -> tuple[pd.DataFrame, list[StageResult]]:
    client = model or LocalModel()
    schema = _schema_raw(df, client)
    current = schema.dataframe
    structured = run_structured(current)
    current = structured.dataframe
    stages = [schema, structured]
    for column in list(current.columns):
        base = re.sub(r"_\d+$", "", str(column))
        category = next((value for key, value in CATEGORY_NAMES.items() if key in base), None)
        if not category:
            continue
        prepared, vault = prepare_private_data(current)
        try:
            category_result = run_categories(prepared, column, category, model=client)
            category_result.dataframe = restore_identities(category_result.dataframe, vault)
            category_result.dataframe.attrs.update(current.attrs)
            current = category_result.dataframe
            stages.append(category_result)
        except (ModelError, ValueError) as exc:
            skipped = StageResult(current.copy(deep=True), "categories")
            skipped.issues.append(
                {"column": column, "rule": "category_model_failed", "message": str(exc)}
            )
            stages.append(skipped)
    schema_columns = schema.details.get("columns", [])
    text_columns = [
        current.columns[item["column_index"]]
        for item in schema_columns
        if item.get("column_type") == "free_text" and item["column_index"] < len(current.columns)
    ]
    if text_columns:
        text_result = run_text(current, list(dict.fromkeys(text_columns)))
    else:
        text_result = StageResult(current.copy(deep=True), "text")
        text_result.details = {"selected_columns": [], "reason": "none detected"}
    current = text_result.dataframe
    stages.append(text_result)
    validation = run_validation(current)
    stages.append(validation)
    return current, stages


def run_pipeline(input_path, output_dir, *, model=None) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    summary = {"tables": [], "skipped_empty_sheets": 0, "failed_tables": 0}
    for path, sheet in discover_tables(input_path):
        try:
            df = read_table(path, sheet=sheet or 0)
        except ValueError as exc:
            if "empty" in str(exc):
                summary["skipped_empty_sheets"] += 1
                continue
            raise
        name = _safe_name(path, sheet)
        try:
            cleaned, stages = run_table(df, model=model)
            data_path = output / f"{name}.cleaned.csv"
            cleaned.to_csv(data_path, index=False, encoding="utf-8-sig")
            report = {
                "source": {"file": path.name, "sheet": sheet},
                "rows": len(cleaned),
                "columns": len(cleaned.columns),
                "pipeline_completed": True,
                "pipeline_validated": not stages[-1].issues,
                "stages": [stage.report() for stage in stages],
            }
            (output / f"{name}.report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            summary["tables"].append(
                {
                    "source_file": path.name,
                    "sheet": sheet,
                    "output": data_path.name,
                    "rows": len(cleaned),
                    "columns": len(cleaned.columns),
                    "changes": sum(len(stage.changes) for stage in stages),
                    "issues": sum(len(stage.issues) for stage in stages),
                    "model_fallback": any(
                        any(i.get("rule") == "schema_model_fallback" for i in stage.issues)
                        for stage in stages
                    ),
                }
            )
        except Exception as exc:
            summary["failed_tables"] += 1
            summary["tables"].append(
                {
                    "source_file": path.name,
                    "sheet": sheet,
                    "error": "table_processing_failed",
                    "error_type": type(exc).__name__,
                }
            )
    summary["processed_tables"] = sum("output" in table for table in summary["tables"])
    summary["total_rows"] = sum(table.get("rows", 0) for table in summary["tables"])
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
