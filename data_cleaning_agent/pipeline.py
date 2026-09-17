"""End-to-end orchestration for folders containing CSV and Excel form exports."""

import hashlib
import json
import re
import time
from pathlib import Path

import pandas as pd

from .adaptive import run_adaptive
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
    "categories": "implemented with reviewed mappings before local-Qwen normalization",
    "text": "implemented with in-place cleanup and audit-only missing flags",
    "validation": "implemented as read-only checks",
    "privacy": "implemented as local in-memory masking before model calls",
}

CATEGORY_NAMES = {
    "university": "University",
    "university_name": "University",
    "branch": "Branch",
    "campus": "Branch",
    "major": "Major",
    "committee": "Committee",
    "committee_name": "Committee",
    "skills": "Skills",
    "tools": "Tools",
    "programming_languages": "Programming languages",
    "role": "Roles",
    "preferred_role": "Roles",
    "department": "Departments",
    "department_name": "Departments",
    "target_areas": "Departments",
}

HEADER_ALIASES = {
    "full_name_ar": {"الاسم الثلاثي بالعربي", "الاسم بالعربي"},
    "full_name_en": {"full name in english", "english name"},
    "gender": {"gender", "الجنس"},
    "phone": {"phone", "phone number", "رقم الجوال", "رقم الهاتف"},
    "email": {"email", "e mail", "البريد الالكتروني gmail", "البريد الإلكتروني gmail"},
    "university": {"university", "university name", "اسم الجامعة", "الجامعة"},
    "major": {"major", "التخصص الجامعي", "التخصص"},
    "university_id": {"university id", "student id", "الرقم الجامعي"},
}

IDENTITY_COLUMN = re.compile(
    r"(?:name|email|phone|university_id|student_id|(?:^|_)id(?:_|$)|الاسم|البريد|الجوال|الرقم)",
    re.I,
)
PADDING_VALUES = {"false", "absent"}


def _header_key(value) -> str:
    return re.sub(r"[^\w\u0600-\u06ff]+", " ", str(value).casefold()).strip()


def _remove_embedded_headers(df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
    result = StageResult(df.copy(deep=True), "embedded_headers")
    positions = {
        i: {_header_key(v) for v in HEADER_ALIASES.get(re.sub(r"_\d+$", "", str(name)), ())}
        for i, name in enumerate(df.columns)
    }
    remove = []
    for row_index, row in df.iterrows():
        matches = sum(
            bool(positions[i]) and _header_key(value) in positions[i]
            for i, value in enumerate(row)
            if not pd.isna(value) and str(value).strip()
        )
        if matches >= 3:
            remove.append(row_index)
    if remove:
        result.dataframe = df.drop(index=remove).reset_index(drop=True)
        result.changes.append(
            {
                "rule": "embedded_headers_removed",
                "count": len(remove),
                "row_indices": remove,
            }
        )
    result.details = {"removed_rows": remove}
    return result.dataframe, result


def _remove_padding_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
    """Remove blank and status-only spreadsheet padding approved by the project owner."""
    result = StageResult(df.copy(deep=True), "padding_rows")
    identity_positions = [
        i for i, column in enumerate(df.columns) if IDENTITY_COLUMN.search(str(column))
    ]
    remove = []
    reasons = {}
    for row_index, row in df.iterrows():
        values = [str(value).strip() for value in row if not pd.isna(value) and str(value).strip()]
        if not values:
            remove.append(row_index)
            reasons[row_index] = "blank_row"
            continue
        identity_blank = all(
            pd.isna(row.iloc[i]) or not str(row.iloc[i]).strip() for i in identity_positions
        )
        if identity_blank and all(value.casefold() in PADDING_VALUES for value in values):
            remove.append(row_index)
            reasons[row_index] = "status_only_padding"
    if remove:
        result.dataframe = df.drop(index=remove).reset_index(drop=True)
        counts = {reason: list(reasons.values()).count(reason) for reason in set(reasons.values())}
        result.changes.append(
            {"rule": "padding_rows_removed", "count": len(remove), "reason_counts": counts}
        )
    result.details = {"removed_rows": remove, "reasons": reasons}
    return result.dataframe, result


def _trim_scalar_whitespace(df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
    result = StageResult(df.copy(deep=True), "whitespace")
    for column_index in range(len(df.columns)):
        result.dataframe.isetitem(
            column_index, result.dataframe.iloc[:, column_index].astype(object).copy()
        )
        for row_index, value in enumerate(df.iloc[:, column_index]):
            if not isinstance(value, str):
                continue
            trimmed = value.strip()
            if trimmed != value:
                result.dataframe.iat[row_index, column_index] = trimmed
                result.changes.append(
                    {
                        "row_index": row_index,
                        "column_index": column_index,
                        "before": value,
                        "after": trimmed,
                    }
                )
    return result.dataframe, result


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


def run_table(
    df: pd.DataFrame, *, model=None, progress=None
) -> tuple[pd.DataFrame, list[StageResult]]:
    notify = progress or (lambda _stage: None)
    client = model or LocalModel()
    notify("schema")
    schema = _schema_raw(df, client)
    current = schema.dataframe
    current, embedded_headers = _remove_embedded_headers(current)
    current, padding_rows = _remove_padding_rows(current)
    current, whitespace = _trim_scalar_whitespace(current)
    notify("adaptive")
    adaptive = run_adaptive(current, model=client)
    current = adaptive.dataframe
    notify("structured")
    structured = run_structured(current)
    current = structured.dataframe
    stages = [schema, embedded_headers, padding_rows, whitespace, adaptive, structured]
    for column in list(current.columns):
        base = re.sub(r"_\d+$", "", str(column))
        category = CATEGORY_NAMES.get(base)
        if not category:
            continue
        prepared, vault = prepare_private_data(current)
        notify("categories")
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
        notify("text")
        text_result = run_text(current, list(dict.fromkeys(text_columns)), append_columns=False)
    else:
        text_result = StageResult(current.copy(deep=True), "text")
        text_result.details = {"selected_columns": [], "reason": "none detected"}
    current = text_result.dataframe
    stages.append(text_result)
    notify("validation")
    validation = run_validation(current)
    stages.append(validation)
    return current, stages


def run_pipeline(input_path, output_dir, *, model=None, progress=None) -> dict:
    pipeline_started = time.perf_counter()
    shared_model = model or LocalModel()
    owns_model = model is None
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    summary = {"tables": [], "skipped_empty_sheets": 0, "failed_tables": 0}
    tables = list(discover_tables(input_path))
    total = len(tables)
    for table_index, (path, sheet) in enumerate(tables):
        table_started = time.perf_counter()
        if progress:
            progress(
                {
                    "event": "table",
                    "table_index": table_index,
                    "total_tables": total,
                    "file": path.name,
                    "sheet": sheet,
                    "stage": "reading",
                }
            )
        try:
            df = read_table(path, sheet=sheet or 0)
        except ValueError as exc:
            if "empty" in str(exc):
                summary["skipped_empty_sheets"] += 1
                continue
            raise
        name = _safe_name(path, sheet)
        try:
            cleaned, stages = run_table(
                df,
                model=shared_model,
                progress=(
                    lambda stage, i=table_index, p=path, s=sheet: progress(
                        {
                            "event": "stage",
                            "table_index": i,
                            "total_tables": total,
                            "file": p.name,
                            "sheet": s,
                            "stage": stage,
                        }
                    )
                )
                if progress
                else None,
            )
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
                    "duration_seconds": round(time.perf_counter() - table_started, 3),
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
    summary["duration_seconds"] = round(time.perf_counter() - pipeline_started, 3)
    if hasattr(shared_model, "metrics"):
        summary["model_metrics"] = dict(shared_model.metrics)
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if progress:
        progress(
            {"event": "complete", "table_index": total, "total_tables": total, "stage": "complete"}
        )
    if owns_model and hasattr(shared_model, "close"):
        shared_model.close()
    return summary
