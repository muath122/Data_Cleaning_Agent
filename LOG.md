# Project change log

Record each logical change, why it was made, checks performed, and remaining limitations.
Never include applicant values or model output from real data.

## 2026-09-09 — Shared local model foundation

- Added a cross-platform Python package, strict response contracts, and a shared llama.cpp client.
- Added `start.py`: creates a uv environment, installs requirements, checks the pinned Qwen GGUF cache,
  downloads missing weights, and starts a localhost-only server. The llama.cpp binary remains a separate prerequisite.
- Added runtime/development requirements and focused ignore rules for private inputs and generated artifacts.
- Preserved Qwen3.5-2B with UD-IQ2_XXS quantization; the filename and revision were verified against the model repository.
- Extracted role prompts into Markdown, preserving the existing schema and category instructions.
- Validation: 15 runtime/client/prompt tests passed; startup help and `git diff --check` passed.
- The model filename/revision was verified online. Real model download/inference has not yet been exercised locally.
- Remaining: reusable stages, CLI, privacy/validation scaffolds, documentation, and tests.

## 2026-09-09 — Reusable stages and command-line workflow

- Migrated schema, category, and text functionality into one package and removed obsolete root demo scripts.
  Original implementations remain in Git history; the original notebook is preserved under `notebooks/` with outputs cleared.
- Schema now validates coverage, indices, source names, confidence, and collisions before renaming.
- Category mappings are batched over unique scalar values, validated before application, and leave ambiguous/multi-value inputs unchanged.
- Text preserves language and original columns, requires explicit target columns, and makes enrichment/masking opt-in.
- Added CSV/XLSX stage exports, JSON change reports, source positions, sheet/header selection, and overwrite protection.
- Added prepared-input contracts and explicit privacy/structured/validation placeholders. The unfinished pipeline fails clearly.
- Added invented examples and migration notes. Real data stays untouched and ignored.
- Validation: 38 automated tests passed; Ruff checks/formatting passed. Tests cover mixed sheet layouts,
  checkbox-only rows, leading-zero strings, literal Excel strings, schema failures, batching, and private-input blocking.
- Remaining: expanded architecture/contribution documentation, dataset findings, CI, and startup verification.

## 2026-09-09 — Team documentation and cross-platform checks

- Expanded README setup, configuration, role status, examples, architecture explanation, and repository guide.
- Added architecture/contracts, aggregate data findings, contributor instructions, and prompt documentation.
- Added GitHub Actions for Python 3.11 on Windows and Linux using uv requirements installation.
- Documented the distinction between prepared-input attestation and actual anonymization, and between stage completion and dataset validation.
- Validation: local unit tests, Ruff checks, and synthetic CLI export pass; hosted CI results are pending the push.
- Startup's real model-download check is in progress; no live inference result is claimed.

## 2026-09-09 — Startup verification and final regression check

- Ran `python3 start.py --download-only`: uv requirements installation completed and the pinned Qwen model downloaded successfully.
- Ran the runtime with `--offline --download-only`: the cached model was reused successfully without a network download.
- Added a regression case preserving distinct conditional-branch columns and skipped answers.
- Validation: 39 tests passed locally; Ruff and diff checks passed. A synthetic XLSX stage export was verified.
- Live inference remains untested here because `llama-server` is not installed. Startup reports the prerequisite and retains cached weights.
- Windows/Linux CI is configured, but its remote status could not be read: the GitHub connector returned 404 for this repository's Actions endpoint.
- All changes were committed and pushed in logical increments; real inputs, generated outputs, and model weights remain outside Git.
