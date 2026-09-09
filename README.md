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

Windows with a manually extracted llama.cpp release:

```powershell
$env:LLAMA_SERVER = "C:\tools\llama.cpp\llama-server.exe"
py -3 start.py
```

```bash
python start.py --download-only
```

The default is `unsloth/Qwen3.5-2B-GGUF`, file `Qwen3.5-2B-UD-IQ2_XXS.gguf`, at a
pinned revision. Models live in ignored `models/`. The startup installs weights,
not the platform-specific llama.cpp executable; a missing executable produces setup guidance.

### Configuration and troubleshooting

| Setting | Default / purpose |
| --- | --- |
| `LLAMA_SERVER` | `llama-server` on PATH; override with an executable path |
| `QWEN_MODEL_REPO` | `unsloth/Qwen3.5-2B-GGUF` |
| `QWEN_MODEL_FILE` | `Qwen3.5-2B-UD-IQ2_XXS.gguf` |
| `QWEN_MODEL_REVISION` | Pinned Hub commit; update with repo/file when changing models |
| `QWEN_MODEL_ALIAS` | `qwen-cleaner`, shared by server and client |
| `QWEN_BASE_URL` | Client URL, `http://127.0.0.1:8080`; localhost only |
| `--port` / `--context-size` | Startup flags, 8080 / 16384 |

After changing the port, update `QWEN_BASE_URL` in the client terminal too. For
offline inference after dependencies and weights are installed, run
`uv run --offline --no-project python -m data_cleaning_agent.runtime --offline`.
An interrupted model download can resume by rerunning startup. If GGUF validation
reports corruption, remove the affected local model cache and retry. If llama.cpp
rejects the architecture or flags, install a recent compatible release.

Memory and speed depend on the machine. The 2-bit model's semantic accuracy needs
evaluation; a larger quantization can be configured without changing stage code.

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
| Structured data | Local phone/email/ID/gender/level/date/attendance/boolean rules; university formatting and review proposals |
| Skills/categories | Validated scalar mappings for a selected column/category; ambiguous and multi-value answers flagged |
| Text | Whitespace/placeholder cleanup; optional local masking, sentiment, and keywords |
| Validation | Draft role and explicit placeholder; final data validation not implemented |
| Privacy/integration | Prepared-input boundary and readiness checks; automatic masking/restoration and full pipeline pending |

`pipeline` exits with an explanation of missing privacy and validation components. Model-backed stages require
synthetic or manually sanitized JSON. Raw Excel/CSV model execution is blocked until
the privacy layer exists. That JSON marker is an attestation, not automatic anonymization.

Agent 2 can run on raw CSV/XLSX without Qwen:

```bash
uv run python main.py stage structured --input examples/structured.csv --output outputs/structured-demo.csv
uv run python main.py stage structured --input examples/structured.csv --field "consent=boolean" --output outputs/consent-demo.csv
uv run python main.py batch-structured --input data --output-dir outputs/agent2-batch
```

Without `--field`, conservative header aliases select known roles; with it, only
the specified fields are processed. See [Agent 2 rules and batch usage](docs/structured-data.md).
The full pipeline still needs automatic privacy preparation/restoration and final validation.

## How the model edits data

Qwen proposes mappings such as `علوم الحاسب → Computer Science` in structured JSON.
Python checks the response, updates a dataframe copy, records changes, and exports
it with pandas. The model does not receive filesystem access or execute generated code.
Markdown defines each role; Python implements its capabilities and limits.

## Repository guide

| Location | Purpose |
| --- | --- |
| `data_cleaning_agent/` | Shared client, contracts, stages, CLI, and startup runtime |
| `prompts/` | Five specialized Markdown role definitions |
| `examples/` | Invented inputs and runnable stage commands |
| `tests/` | Model-independent regression tests |
| `notebooks/` | Original text experiment, kept as historical reference |
| `docs/` | Architecture and aggregate spreadsheet findings |
| `data/`, `models/`, `outputs/` | Ignored local inputs, weights, and results |

Start with [architecture](docs/architecture.md), [dataset findings](docs/data-notes.md),
[contribution guidance](CONTRIBUTING.md), and [the change log](LOG.md).

The local sheets include conditional form branches, generic headers, mixed numeric/text
identifiers, repeated exports, and checkbox-only rows. The cleanup preserves these
cases for explicit handling; it does not automatically merge sheets or remove records.
Text exports retain original values and reports can contain them. Optional masking
does not make the exported dataset anonymous.
