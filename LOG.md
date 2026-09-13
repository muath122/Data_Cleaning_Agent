# Project change log

Record each logical change, why it was made, checks performed, and remaining limitations.
Never include applicant values or model output from real data.

## 2026-09-13 — Complete pipeline and KAUST GPU runner

- Added end-to-end CSV/XLSX folder orchestration across all five roles.
- Added local in-memory identifier masking before Qwen calls and restoration
  before export; model access remains restricted to localhost.
- Implemented read-only duplicate, missing-value, email, and phone validation.
- Added per-sheet cleaned CSVs, JSON audit reports, and an aggregate run summary.
- Added a Slurm V100 job that installs uv dependencies, builds CUDA llama.cpp,
  starts the pinned Qwen model, runs `data/`, and shuts the server down.
- Configured the job for the account's permitted `debug` GPU queue after Ibex
  rejected the general GPU partitions; the queue has a two-hour limit.
- Made repeated submissions reuse the existing uv environment after the first
  cluster run exposed uv's existing-environment guard.
- Pointed the CUDA build at Ibex's versioned CUDA 12.4.1 software tree after
  confirming `/usr/local/cuda` contains no compiler on compute nodes.
- Serialized native Excel date/time objects before model validation and removed
  exception details from summaries after the first data pass exposed that boundary.
- Added an end-to-end regression test that verifies source preservation,
  privacy restoration, semantic mapping, structured normalization, and text cleanup.

## PR #4 — Integrate Amirah's structured-data agent

- Merged Amirah's PR ancestry and resolved the requirements conflict by retaining the shared uv-compatible dependencies; removed her unused NumPy import.
- Moved structured rules, Arabic/English aliases, university helpers, and batch handling into the current package.
- Connected Agent 2 to StageResult, CLI, schema-compatible column roles, source-position reports, and existing safe exports.
- Tightened numeric/date/ID handling: avoid partial academic-level matches, ambiguous date parsing, invented ID digits, and value-based boolean guesses in unrelated columns.
- Preserved distinct personal/university emails and conditional/repeated columns. Unknown values remain for review.
- University case/whitespace equivalence is applied; fuzzy and shared-Qwen comparisons are review-only. Model assistance requires PreparedData.
- Replaced destructive ZIP extraction/output cleanup with in-memory XLSX reads and new-directory exports; duplicate basenames retain separate outputs.
- Added runnable examples and Agent 2 documentation. Pipeline readiness now lists only privacy/restoration and final validation as missing prerequisites.
- Validation: 84 automated tests, Ruff checks, formatting, diff checks, and the synthetic structured CLI export passed.
- An in-memory check processed all 17 non-empty local sheets (2 empty sheets skipped for the check), preserving all 2,334 rows and source columns. No source files were written and no model calls were made.
- Integration preserves Amirah's original commit ancestry. Remote main and PR head were checked before publishing; GitHub API/browser access was unavailable, so publishing uses the authenticated Git remote.

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
