"""Command-line access to stage experiments and pipeline readiness."""

import argparse
import json
import zipfile
from pathlib import Path
from typing import get_args

from pydantic import ValidationError

from .contracts import Category
from .io import check_outputs, export_result, read_table
from .model import ModelError
from .pipeline import STAGE_STATUS, run_pipeline
from .privacy import PrivacyNotReady, prepare_private_data, read_prepared
from .stages.categories import run_categories
from .stages.schema import run_schema
from .stages.structured import run_structured
from .stages.text import run_text
from .structured.batch import process_input


def parser():
    root = argparse.ArgumentParser(
        description="Run the local data-cleaning pipeline or an individual stage."
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Show implemented and missing stages")
    pipeline = commands.add_parser("pipeline", help="Clean every CSV/XLSX table in a file/folder")
    pipeline.add_argument("--input", type=Path, required=True)
    pipeline.add_argument("--output-dir", type=Path, required=True)
    stage = commands.add_parser("stage", help="Run one implemented stage")
    stage.add_argument("name", choices=["schema", "structured", "categories", "text"])
    inputs = stage.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--input", type=Path, help="Raw CSV/XLSX; deterministic text/structured stages"
    )
    inputs.add_argument(
        "--sanitized-input", type=Path, help="Explicitly prepared JSON; see examples/README.md"
    )
    stage.add_argument("--output", required=True, type=Path)
    sheets = stage.add_mutually_exclusive_group()
    sheets.add_argument("--sheet", help="Exact Excel sheet name")
    sheets.add_argument("--sheet-index", type=int, default=0, help="Zero-based Excel sheet index")
    stage.add_argument("--header-row", type=int, default=1, help="One-based source header row")
    stage.add_argument(
        "--column",
        action="append",
        default=[],
        help="Repeat for multiple text columns; exactly one for categories",
    )
    stage.add_argument("--category", choices=get_args(Category))
    stage.add_argument(
        "--enrich", action="store_true", help="Text only: add heuristic sentiment/topics"
    )
    stage.add_argument(
        "--mask-pii",
        action="store_true",
        help="Text only: mask patterns in appended text, keeping original columns",
    )
    stage.add_argument(
        "--field",
        action="append",
        default=[],
        help="Structured only: COLUMN=ROLE; repeat to select fields",
    )
    stage.add_argument(
        "--judge-universities",
        action="store_true",
        help="Structured only: prepared input, Qwen review proposals",
    )
    batch = commands.add_parser(
        "batch-structured", help="Normalize an XLSX folder/ZIP using local rules"
    )
    batch.add_argument("--input", type=Path, required=True)
    batch.add_argument("--output-dir", type=Path, required=True)
    batch.add_argument("--field", action="append", default=[])
    batch.add_argument("--header-row", type=int, default=1)
    batch_sheets = batch.add_mutually_exclusive_group()
    batch_sheets.add_argument("--sheet")
    batch_sheets.add_argument("--sheet-index", type=int, default=0)
    return root


def field_roles(fields):
    if not fields:
        return None
    roles = {}
    for field in fields:
        name, separator, role = field.rpartition("=")
        if not separator or not name or not role or name in roles:
            raise ValueError("Use distinct COLUMN=ROLE values for --field")
        roles[name] = role
    return roles


def main(argv=None):
    root = parser()
    args = root.parse_args(argv)
    try:
        if args.command == "status":
            print(json.dumps(STAGE_STATUS, ensure_ascii=False, indent=2))
            return 0
        if args.command == "pipeline":
            summary = run_pipeline(args.input, args.output_dir)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if summary["failed_tables"] == 0 else 2
        if args.sheet_index < 0 or args.header_row < 1:
            raise ValueError("Sheet index must be nonnegative and header row must be positive")
        if args.command == "batch-structured":
            archive, results = process_input(
                args.input,
                args.output_dir,
                field_roles(args.field),
                sheet=args.sheet if args.sheet is not None else args.sheet_index,
                header_row=args.header_row,
            )
            print(f"Structured batch complete: {len(results)} tables. Full pipeline has not run.")
            print(archive)
            return 0
        if args.name != "structured" and (args.field or args.judge_universities):
            raise ValueError("--field and --judge-universities are structured-stage options")
        if args.name == "structured" and (args.column or args.category):
            raise ValueError("Structured uses --field COLUMN=ROLE, not --column or --category")
        if args.name != "text" and (args.enrich or args.mask_pii):
            raise ValueError("--enrich and --mask-pii are text-stage options")
        if args.name == "schema" and (args.column or args.category):
            raise ValueError("Schema uses all columns; omit --column and --category")
        if args.name == "text" and (not args.column or args.category):
            raise ValueError("Text requires --column; --category is not applicable")
        if args.name == "categories" and (len(args.column) != 1 or not args.category):
            raise ValueError("Categories requires exactly one --column and a --category")
        source = args.input or args.sanitized_input
        check_outputs(args.output, args.name, source)
        if args.sanitized_input:
            if args.sheet is not None or args.sheet_index != 0 or args.header_row != 1:
                raise ValueError("Sheet and header options apply only to raw table input")
            prepared = read_prepared(args.sanitized_input)
            df = prepared.dataframe()
            df.attrs["source"] = {"file": source.name, "provenance": prepared.provenance}
        else:
            df = read_table(
                args.input,
                sheet=args.sheet if args.sheet is not None else args.sheet_index,
                header_row=args.header_row,
            )
            prepared, _vault = prepare_private_data(df)
        if args.name == "schema":
            result = run_schema(prepared)
        elif args.name == "categories":
            result = run_categories(prepared, args.column[0], args.category)
        elif args.name == "structured":
            result = run_structured(
                prepared if (args.sanitized_input or args.judge_universities) else df,
                field_roles(args.field),
                judge_universities=args.judge_universities,
            )
        else:
            result = run_text(df, args.column, enrich=args.enrich, mask_pii=args.mask_pii)
        result.dataframe.attrs.update(df.attrs)
        paths = export_result(result, args.output, source=source)
        print(f"Stage complete ({len(result.issues)} review issues). Full pipeline has not run.")
        for path in paths:
            print(path)
        return 0
    except ValidationError:
        print("Error: prepared input does not match the documented JSON contract.")
        return 2
    except (
        ModelError,
        PrivacyNotReady,
        NotImplementedError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
