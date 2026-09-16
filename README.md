# Sift — Local Data Cleaning Agent

Sift turns messy Arabic and English workshop or membership form exports into
clean, reviewable CSV files. One local **Qwen3.5-2B** instance supplies semantic
judgment, deterministic Python handles known high-risk formats, and every applied
change or unresolved issue is recorded in a JSON audit report. Direct identifiers
are masked before inference and source files are never overwritten.

## The five agents

The agents are five specialized prompts served sequentially by the same local Qwen
instance—not five model processes:

1. **Schema Agent** understands each column and proposes a stable English schema.
2. **Structured Data Agent** standardizes phones, emails, dates, IDs, gender,
   attendance, academic levels, and booleans using deterministic rules.
3. **Category Agent** unifies equivalent universities, majors, committees, skills,
   tools, programming languages, roles, and departments.
4. **Text Agent** removes mechanical noise from open responses without translating,
   summarizing, or changing their intended meaning.
5. **Validation Agent** performs read-only checks for missing, malformed, duplicate,
   or uncertain records.

A guarded **adaptive planner** complements those roles. It can detect unfamiliar
structural patterns and compose a small allowlisted cleaning plan. Python applies
only high-confidence, low-risk mechanical operations; identity changes, semantic
guesses, large edits, and every row-removal proposal remain review-only. The model
cannot generate executable code, access files, or modify a source workbook.

## Run locally

Install [uv](https://docs.astral.sh/uv/) and a recent
[llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server`, then run:

```bash
python start.py
```

Open **http://127.0.0.1:7860**, drop in CSV/XLSX files, follow the five roles plus
adaptive discovery, review the changes, and download the cleaned tables. Source files are
never overwritten. Command-line users can run `uv run python -m
data_cleaning_agent pipeline --input data --output-dir outputs/local-run`.

`start.py` creates `.venv`, installs `requirements.txt`, downloads the pinned
`Qwen3.5-2B-Q4_K_M.gguf` when missing, and serves it only on localhost. The
4-bit file is about 1.28 GB and was selected for reliable structured output.
The pipeline accepts CSV files, Excel files, or a folder containing both. Each
nonempty Excel sheet becomes a cleaned CSV plus a JSON audit report.
Known university, major, and committee aliases come from
`knowledge_base/knowledge_base_v0.3.json` before Qwen reviews unknown values.
Cleaning keeps the source column count and records missing answers in the audit
report instead of adding helper columns. Blank spreadsheet padding and rows that
only contain absent/false attendance flags are removed. Multi-value categories
are normalized item by item and kept in their original order. Set
`DATA_CLEANING_KNOWLEDGE_BASE` to use another reviewed JSON knowledge base.

### CPU performance

Sift reuses one model connection for the whole run, caches repeated requests,
batches up to 20 unknown category values, and uses smaller output budgets per role.
`llama-server` defaults to at most eight CPU threads with a 512-token batch. Override
these settings when benchmarking a specific machine:

```bash
QWEN_THREADS=4 QWEN_BATCH_SIZE=256 QWEN_UBATCH_SIZE=64 python start.py
```

The result summary separates total runtime from model request time and counts model
requests/cache hits. First launch may also include the one-time model download and
server startup, which should not be compared with a warm cleaning run.

See the public, invented-data showcase at
**https://muath122.github.io/Data_Cleaning_Agent/**. It contains no participant data.

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

The model suggests semantic mappings and allowlisted cleanup plans; it never edits files or runs code.
Deterministic Python performs phone, email, gender, ID, academic-level,
timestamp, attendance, and boolean normalization. Uncertain values remain in
place and appear in review reports. See [LOG.md](LOG.md) for implementation
history and `prompts/` for each role contract.

The latest GPU results are summarized in [ANALYSIS_REPORT.md](ANALYSIS_REPORT.md).
The remaining values requiring human review are listed in [EDGE_CASES.md](EDGE_CASES.md).
