# Local Data Cleaning Agent

Prepare Arabic and English form exports for analysis using one local Qwen model,
specialized Markdown instructions, and Python transformations. Original datasets
stay separate from stage outputs. This is a team prototype, not a complete cleaning pipeline.

## Local Qwen startup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and a recent
[llama.cpp release](https://github.com/ggml-org/llama.cpp/releases) supporting Qwen3.5.
On macOS, `brew install llama.cpp` provides `llama-server`. On Windows, extract the
appropriate release and add its executable directory to PATH, or set `LLAMA_SERVER`
to the full path to `llama-server.exe`.

From the repository root, run:

```bash
python start.py
```

Use `python3` on macOS/Linux if needed, or `py -3` on Windows. The script uses uv to
create `.venv` with Python 3.11, installs `requirements.txt`, checks the local model
cache, downloads missing Qwen weights, and starts the server on `127.0.0.1:8080`.
Keep this terminal open. The first run needs internet; inference runs locally.

```bash
python start.py --download-only
```

The default is `unsloth/Qwen3.5-2B-GGUF`, file `Qwen3.5-2B-UD-IQ2_XXS.gguf`, at a
pinned revision. Models live in ignored `models/`. The startup installs weights,
not the platform-specific llama.cpp executable; a missing executable produces setup guidance.

## Development

```bash
uv venv --python 3.11
uv pip install -r requirements-dev.txt
uv run --no-project python -m pytest tests
```

Dependencies remain in requirements files and can also be installed with pip.
See [LOG.md](LOG.md) for incremental implementation status. No real datasets or
model weights belong in Git.

## Run a stage

```bash
uv run --no-project python -m data_cleaning_agent status
uv run --no-project python -m data_cleaning_agent stage text --input examples/synthetic.csv --column feedback --output outputs/demo.csv
```

This produces a separate CSV and JSON report with `.text` in their names. Source
files are preserved. Reports identify changed cells and review issues and explicitly
state that the full pipeline has not validated the dataset.

See [examples](examples/README.md) for schema and category commands, prepared JSON,
Excel sheet/header selection, and optional text enrichment.

| Stage | Current implementation |
| --- | --- |
| Schema | Context, model proposals, validated renaming by column index; cross-file reconciliation pending |
| Structured data | Draft role and explicit placeholder; phone/email/date normalization not implemented |
| Skills/categories | Validated scalar mappings for a selected column/category; ambiguous and multi-value answers flagged |
| Text | Whitespace/placeholder cleanup; optional local masking, sentiment, and keywords |
| Validation | Draft role and explicit placeholder; final data validation not implemented |
| Privacy/integration | Prepared-input boundary and readiness checks; automatic masking/restoration and full pipeline pending |

`pipeline` exits with an explanation of missing stages. Model-backed stages require
synthetic or manually sanitized JSON. Raw Excel/CSV model execution is blocked until
the privacy layer exists. That JSON marker is an attestation, not automatic anonymization.
