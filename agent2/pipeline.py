from pathlib import Path
import shutil
import zipfile

import pandas as pd

from .normalizers import (
    infer_supported_role,
    standardize_structure,
)
from .university import (
    apply_dynamic_university_map,
    build_dynamic_university_map,
)


def load_excel_files(input_path):
    """
    Accept either:
      - a ZIP containing Excel files, or
      - a folder containing Excel files.
    Returns {file_name: DataFrame}.
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input not found: {input_path}"
        )

    extraction_folder = None

    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        extraction_folder = (
            input_path.parent
            / f".{input_path.stem}_extracted"
        )

        if extraction_folder.exists():
            shutil.rmtree(extraction_folder)

        extraction_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        with zipfile.ZipFile(input_path, "r") as archive:
            archive.extractall(extraction_folder)

        excel_files = sorted(
            extraction_folder.rglob("*.xlsx")
        )

    elif input_path.is_dir():
        excel_files = sorted(
            input_path.rglob("*.xlsx")
        )

    elif (
        input_path.is_file()
        and input_path.suffix.lower() == ".xlsx"
    ):
        excel_files = [input_path]

    else:
        raise ValueError(
            "Input must be a .zip, .xlsx, or folder."
        )

    if not excel_files:
        raise ValueError(
            "No .xlsx files were found in the input."
        )

    dataframes = {}

    for path in excel_files:
        dataframes[path.name] = pd.read_excel(path)

    return dataframes, extraction_folder


def process_dataframes(dataframes, qwen_pipe=None):
    """
    Run Agent 2 on already-loaded DataFrames.
    """
    structured_files = {}
    report_rows = []

    # Pass 1: structured fields.
    for file_name, df in dataframes.items():
        normalized_df, rows = standardize_structure(df)
        structured_files[file_name] = normalized_df

        for row in rows:
            report_rows.append(
                {"File": file_name, **row}
            )

    # Pass 2: university equivalence across all files.
    university_map = build_dynamic_university_map(
        structured_files,
        qwen_pipe=qwen_pipe,
    )

    structured_files = apply_dynamic_university_map(
        structured_files,
        university_map,
    )

    for file_name, df in structured_files.items():
        university_columns = [
            column
            for column in df.columns
            if infer_supported_role(column) == "university"
        ]

        for column in university_columns:
            report_rows.append(
                {
                    "File": file_name,
                    "Column": column,
                    "Role": "university_dynamic_unification",
                    "Values Changed": "runtime-learned",
                }
            )

    report_df = pd.DataFrame(report_rows)

    return structured_files, report_df


def export_results(
    structured_files,
    report_df,
    output_dir,
    zip_name="Agent2_Standardized_Output.zip",
):
    """
    Save each processed dataset as its own Excel file.
    Package only the standardized Excel files into one ZIP.
    """
    output_dir = Path(output_dir)
    standardized_dir = output_dir / "standardized_files"

    if standardized_dir.exists():
        shutil.rmtree(standardized_dir)

    standardized_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    created_files = []

    for file_name, df in structured_files.items():
        output_name = (
            f"{Path(file_name).stem}_standardized.xlsx"
        )
        output_path = standardized_dir / output_name

        df.to_excel(
            output_path,
            index=False,
            engine="openpyxl",
        )
        created_files.append(output_path)

    # Keep the report in output/ for the team, but do not
    # include it in the ZIP requested for processed Excel files.
    report_path = output_dir / "structure_report.csv"
    report_df.to_csv(
        report_path,
        index=False,
        encoding="utf-8-sig",
    )

    zip_path = output_dir / zip_name

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in created_files:
            archive.write(
                path,
                arcname=path.name,
            )

    return zip_path, created_files, report_path


def process_input(
    input_path,
    output_dir,
    qwen_pipe=None,
):
    """
    Complete Agent 2 pipeline.
    """
    dataframes, extraction_folder = load_excel_files(
        input_path
    )

    try:
        structured_files, report_df = process_dataframes(
            dataframes,
            qwen_pipe=qwen_pipe,
        )

        return export_results(
            structured_files,
            report_df,
            output_dir,
        )

    finally:
        if (
            extraction_folder is not None
            and extraction_folder.exists()
        ):
            shutil.rmtree(extraction_folder)
