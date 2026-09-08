"""Read one explicit table; export separate stage artifacts without overwriting."""

import json
from io import BytesIO
from pathlib import Path

import pandas as pd

from .contracts import StageResult


def read_table(path, *, sheet=0, header_row=1) -> pd.DataFrame:
    path = Path(path)
    if header_row < 1:
        raise ValueError("header-row is one-based and must be positive")
    if path.suffix.lower() == ".csv":
        raw = pd.read_csv(
            path,
            header=None,
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=False,
            encoding="utf-8-sig",
        )
    elif path.suffix.lower() == ".xlsx":
        raw = pd.read_excel(
            path,
            sheet_name=sheet,
            header=None,
            dtype=object,
            keep_default_na=False,
            engine="openpyxl",
        )
    else:
        raise ValueError("Only CSV and XLSX inputs are supported")
    if raw.empty or header_row > len(raw):
        raise ValueError("Selected sheet/header row is empty or outside the table")
    headers = [str(value) if not pd.isna(value) else "" for value in raw.iloc[header_row - 1]]
    df = raw.iloc[header_row:].copy().reset_index(drop=True)
    df.columns = headers
    df.attrs["source"] = {
        "file": path.name,
        "sheet": sheet if path.suffix.lower() == ".xlsx" else None,
        "header_row": header_row,
        "first_data_row": header_row + 1,
    }
    return df


def output_paths(output, stage):
    path = Path(output)
    if path.suffix.lower() not in {".csv", ".xlsx"}:
        raise ValueError("Output must end in .csv or .xlsx")
    stem = path.stem if path.stem.endswith(f".{stage}") else f"{path.stem}.{stage}"
    return path.with_name(stem + path.suffix), path.with_name(stem + ".report.json")


def check_outputs(output, stage, source=None):
    paths = output_paths(output, stage)
    for path in paths:
        if source and path.resolve() == Path(source).resolve():
            raise ValueError("Output cannot replace the source file")
        if path.exists():
            raise FileExistsError(f"Output already exists: {path}")
    return paths


def export_result(result: StageResult, output, *, source=None):
    data_path, report_path = check_outputs(output, result.stage, source)
    report = result.report()
    report["source"] = result.dataframe.attrs.get("source")
    report_bytes = json.dumps(
        report, ensure_ascii=False, indent=2, allow_nan=False, default=str
    ).encode("utf-8")
    if data_path.suffix.lower() == ".csv":
        data_bytes = result.dataframe.to_csv(index=False).encode("utf-8-sig")
    else:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            result.dataframe.to_excel(writer, index=False, sheet_name=result.stage)
            # Preserve strings as literal text, including responses beginning with '='.
            for row in writer.book[result.stage].iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
        data_bytes = buffer.getvalue()
    created = []
    try:
        for path, content in [(data_path, data_bytes), (report_path, report_bytes)]:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                created.append(path)
                handle.write(content)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return data_path, report_path
