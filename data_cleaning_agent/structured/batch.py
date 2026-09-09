"""Folder/ZIP workflow adapted from PR #4 without destructive extraction or exports."""

import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd

from ..io import export_result, read_table
from ..stages.structured import run_structured_many


def load_excel_files(input_path, *, sheet=0, header_row=1):
    path = Path(input_path)
    tables = {}
    if path.is_dir():
        for file in sorted(path.rglob("*")):
            if file.is_file() and file.suffix.lower() == ".xlsx" and not file.name.startswith("~$"):
                key = file.relative_to(path).as_posix()
                tables[key] = read_table(file, sheet=sheet, header_row=header_row)
    elif path.is_file() and path.suffix.lower() == ".zip":
        # Read XLSX members in memory; never extract archive paths to the filesystem.
        with zipfile.ZipFile(path) as archive:
            for member in sorted(archive.infolist(), key=lambda item: item.filename):
                if member.is_dir() or not member.filename.lower().endswith(".xlsx"):
                    continue
                if Path(member.filename).name.startswith("~$"):
                    continue
                if member.filename in tables:
                    raise ValueError("ZIP contains duplicate member names")
                tables[member.filename] = read_table(
                    BytesIO(archive.read(member)),
                    sheet=sheet,
                    header_row=header_row,
                    source_name=member.filename,
                )
    elif path.is_file() and path.suffix.lower() == ".xlsx":
        tables[path.name] = read_table(path, sheet=sheet, header_row=header_row)
    else:
        raise ValueError("Batch input must be an existing XLSX, ZIP, or folder")
    if not tables:
        raise ValueError("No Excel tables were found")
    for name, df in tables.items():
        df.attrs["source"]["file"] = name
    return tables


def process_input(input_path, output_dir, column_roles=None, *, sheet=0, header_row=1):
    source, output = Path(input_path), Path(output_dir)
    if output.exists():
        raise FileExistsError("Batch output directory already exists; choose a new directory")
    if source.is_dir() and source.resolve() in output.resolve().parents:
        raise ValueError("Batch output directory must be outside the input directory")
    tables = load_excel_files(source, sheet=sheet, header_row=header_row)
    results = run_structured_many(tables, column_roles)
    output.mkdir(parents=True, exist_ok=False)
    try:
        created, summaries = [], []
        for i, (name, result) in enumerate(results.items(), 1):
            # Numeric prefixes also avoid collisions between identical basenames.
            filename = f"{i:04d}.xlsx"
            data, report = export_result(result, output / "standardized_files" / filename)
            created.append(data)
            summaries.append(
                {
                    "source": name,
                    "output": data.name,
                    "report": report.name,
                    "rows": len(result.dataframe),
                    "changes": len(result.changes),
                    "issues": len(result.issues),
                    "pipeline_validated": False,
                }
            )
        pd.DataFrame(summaries).to_csv(
            output / "structure_report.csv", index=False, encoding="utf-8-sig"
        )
        archive_path = output / "Agent2_Standardized_Output.zip"
        with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in created:
                archive.write(file, arcname=file.name)
        return archive_path, results
    except Exception:
        # Only remove the new directory owned by this invocation, never a preexisting one.
        shutil.rmtree(output)
        raise
