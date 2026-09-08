"""Command-line access to stage experiments and pipeline readiness."""

import argparse
import json
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
from .stages.text import run_text


def parser():
    root = argparse.ArgumentParser(
        description="Run local data-cleaning stages. Full pipeline is unfinished."
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Show implemented and missing stages")
    commands.add_parser("pipeline", help="Check full-pipeline readiness (currently fails)")
    stage = commands.add_parser("stage", help="Run one implemented stage")
    stage.add_argument("name", choices=["schema", "categories", "text"])
    inputs = stage.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input", type=Path, help="Raw CSV/XLSX; Python-only text stage")
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
    return root


def main(argv=None):
    root = parser()
    args = root.parse_args(argv)
    try:
        if args.command == "status":
            print(json.dumps(STAGE_STATUS, ensure_ascii=False, indent=2))
            return 0
        if args.command == "pipeline":
            run_pipeline()
        if args.sheet_index < 0 or args.header_row < 1:
            raise ValueError("Sheet index must be nonnegative and header row must be positive")
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
        if args.input and args.name != "text":
            prepare_private_data(None)  # Stop before reading or transmitting private input.
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
        if args.name == "schema":
            result = run_schema(prepared)
        elif args.name == "categories":
            result = run_categories(prepared, args.column[0], args.category)
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
    except (ModelError, PrivacyNotReady, NotImplementedError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
