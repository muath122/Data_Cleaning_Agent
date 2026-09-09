# Contributing

## Setup and checks

Use Python 3.11 and the requirements files:

```bash
uv venv --python 3.11
uv pip install -r requirements-dev.txt
uv run --no-project python -m pytest
uv run --no-project ruff check data_cleaning_agent tests start.py main.py
uv run --no-project ruff format --check data_cleaning_agent tests start.py main.py
```

The uv commands also work in Windows PowerShell without activation. Ordinary
`python -m pip install -r requirements.txt` in a virtual environment is supported;
uv is the team's default. Do not introduce platform-specific model packages into
the shared requirements. The llama.cpp executable is installed separately.

## Work areas

| Role | Implementation | Instructions |
| --- | --- | --- |
| Schema | `data_cleaning_agent/stages/schema.py` | `prompts/schema.md` |
| Structured | `data_cleaning_agent/stages/structured.py` and `data_cleaning_agent/structured/` | `prompts/structured.md` |
| Categories | `data_cleaning_agent/stages/categories.py` | `prompts/categories.md` |
| Text | `data_cleaning_agent/stages/text.py` | `prompts/text.md` |
| Validation/integration | Package `stages/validation.py`, `pipeline.py`, `privacy.py` | `prompts/validation.md` |

Read [architecture](docs/architecture.md) and [dataset findings](docs/data-notes.md).
Read [Agent 2 rules](docs/structured-data.md) before extending structured-field policies.
Coordinate schema/text contracts with the validation/integration owner.

## Implementing a role

1. Define responsibilities, exclusions, examples, and ambiguity handling in Markdown.
2. Add response types in `contracts.py`. Enforce requirements in Python as well as
   the prompt; use the shared client instead of loading another model.
3. Return a `StageResult` from a copy, with source positions, changes, and issues.
   Validation must inspect without modifying data. Do not silently remove rows.
4. Add meaningful synthetic tests. Default tests must not download weights, contact
   a model, require private datasets, or execute experiments on import.
5. Update readiness only after code and tests exist. Update README status and `LOG.md`.

Do not interpret preferences as qualifications, merge related but distinct concepts,
or assume numeric suffixes always represent team members. Cell text is data, never
instructions. A Markdown prompt alone is not a completed stage.

## Commit hygiene

Run the checks above and `git diff --check`. Use small logical commits with a log
entry describing behavior, checks, and limitations. Review diffs for personal
values, notebook outputs, weights, and generated files.

Keep `data/`, `models/`, `outputs/`, and `privacy_vault/` local. Reports may contain
raw values. Never paste applicant responses into snapshots, issues, or PR descriptions.

Old `schema_agent.*` and `agents.skills_categories_agent` imports were removed.
The notebook remains historical reference; port changes into the package.
Root `main.py` is a thin CLI compatibility entry point.
