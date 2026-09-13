# Local Data Cleaning Agent

This project cleans Arabic and English workshop form exports with one local
**Qwen3.5-2B** model and five specialized Markdown roles: schema, structured
fields, categories, text, and validation. Python reads and writes the tables,
checks model responses, masks direct identifiers before inference, and keeps
every source file unchanged.

## Run locally

Install [uv](https://docs.astral.sh/uv/) and a recent
[llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server`, then run:

```bash
python start.py
```

In a second terminal:

```bash
uv run python -m data_cleaning_agent pipeline --input data --output-dir outputs/local-run
```

`start.py` creates `.venv`, installs `requirements.txt`, downloads the pinned
`Qwen3.5-2B-Q4_K_M.gguf` when missing, and serves it only on localhost. The
4-bit file is about 1.28 GB and was selected for reliable structured output.
The pipeline accepts CSV files, Excel files, or a folder containing both. Each
nonempty Excel sheet becomes a cleaned CSV plus a JSON audit report.

## Run on KAUST Ibex with a GPU

```bash
ssh gcode
cd /ibex/user/bahajao/Data_Cleaning_Agent
git pull
sbatch scripts/hpc_gpu_job.sh
```

Watch the job with `squeue -u "$USER"`. Results are written to
`outputs/run-<job-id>/`; `summary.json` gives aggregate counts and failures.
The first GPU job builds CUDA-enabled llama.cpp and caches it under `tools/`.

The model suggests semantic mappings; it never edits files or runs code.
Deterministic Python performs phone, email, gender, ID, academic-level,
timestamp, attendance, and boolean normalization. Uncertain values remain in
place and appear in review reports. See [LOG.md](LOG.md) for implementation
history and `prompts/` for each role contract.
