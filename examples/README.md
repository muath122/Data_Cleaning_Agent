# Stage examples

All committed inputs here are invented. `example.invalid` addresses cannot identify applicants.
Run commands from the repository root after installing `requirements.txt`.

## Text cleanup without Qwen

```bash
uv run --no-project python -m data_cleaning_agent stage text --input examples/synthetic.csv --column feedback --output outputs/demo.csv
```

This writes `outputs/demo.text.csv` and `outputs/demo.text.report.json`.
Use a different output name on subsequent runs; existing files are never overwritten.
Add `--enrich` for heuristic sentiment/topics, or `--mask-pii` for pattern masking
in appended text. The original columns remain, so exports and reports remain private.

## Model-backed stages

Start the server with `python start.py` in another terminal, then:

```bash
uv run --no-project python -m data_cleaning_agent stage schema --sanitized-input examples/synthetic.json --output outputs/schema-demo.xlsx
uv run --no-project python -m data_cleaning_agent stage categories --sanitized-input examples/synthetic.json --column التخصص --category Major --output outputs/categories-demo.csv
```

These are opt-in live model smoke tests. Inspect the stage reports; syntax validation
does not establish semantic correctness. Tests under `tests/` mock the model and never download weights.

## Prepared input contract

The JSON envelope has exactly `provenance`, `columns`, and `rows`. Provenance is
`synthetic` or `manually_sanitized`. Rows must match the column count and contain
JSON scalars or null. Keep cell values and labels free of identifying information.

This marker is an explicit caller attestation, not a PII detector. Automatic privacy
preparation and identity restoration are not implemented. Do not copy private rows
into this envelope and claim they are sanitized. Raw CSV/XLSX model commands stop
before reading the file or calling Qwen.

## Excel selection

The default is the first sheet and its first row of headers. Use `--sheet "name"`
or `--sheet-index 1` and `--header-row 2` when appropriate. Generic `Column1`
labels do not prove the next row is a header; inspect the table and select explicitly.
Processing one sheet exports one table, not a reconstructed copy of the workbook.
