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
