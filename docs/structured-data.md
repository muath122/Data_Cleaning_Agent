# Agent 2: structured data

Amirah's PR #4 supplies the structured-field rules, Arabic/English alias tables,
university matching helpers, and folder/ZIP workflow. They are integrated under
`data_cleaning_agent/structured/` and `stages/structured.py`. No separate model loader
or second export pipeline is needed. NumPy was an unused PR import, so no additional
direct dependency was added to the shared requirements.

## Run a selected table

```bash
uv run python main.py stage structured --input examples/structured.csv --output outputs/agent2.csv
uv run python main.py stage structured --input data/input.xlsx --sheet-index 1 --header-row 2 --field "رقم الجوال=phone" --field "هل ستحضر؟=attendance" --output outputs/selected.xlsx
```

Without `--field`, exact normalized header aliases select roles, including numbered
fields, personal/university email, and canonical snake_case names. Unrecognized
columns remain untouched; no boolean role is guessed from values like 0/1 or yes/no.
Supplying `--field COLUMN=ROLE` selects only those explicit columns. Repeat the flag
as needed. Duplicate selected column names must be resolved before processing.

Roles: `phone`, `email`, `gender`, `university_id`, `academic_level`, `timestamp`,
`attendance`, `boolean`, and `university`. This stage does not rename columns.

## Rules and limits

| Field | Applied changes | Preserved for review |
| --- | --- | --- |
| Phone | Saudi mobile prefixes +966/00966/966/05 or nine digits beginning with 5; Arabic/Persian digits; spaces, hyphens, parentheses | Unsupported countries, invalid lengths, fractional numbers, other text |
| Email | Outer whitespace, lowercase domain | Embedded whitespace, invalid shape; local-part case is preserved |
| Gender | Known English/Arabic aliases to Male/Female | Unknown or self-described responses |
| University ID | Digit normalization, outer whitespace, integral numeric value to text | Fractional/ambiguous values; numeric IDs are flagged because leading digits may already be lost |
| Academic level | Whole explicit levels 1–10, Arabic ordinals | Study years, ranges, partial matches, unsupported levels |
| Timestamp | Native dates and ISO year-first text, retaining timezone/precision | Numeric serials/epochs, ambiguous day/month text, invalid dates |
| Attendance | Explicit booleans and aliases to Present/Absent/Late/Excused | Unknown responses |
| Boolean | Known aliases and explicit 0/1 | Other values; missing remains missing |
| University | Whitespace/case formatting and equivalent observed spellings across tables | Fuzzy or semantic equivalences require review |

The Saudi phone and academic-level ranges are local policies, not universal rules.
No required-answer inference, duplicate removal, applicant scoring, or final validation
occurs. Blank conditional answers and checkbox-only rows are retained. Read the report
before using the output. Original source files remain untouched.

## University review with Qwen

```bash
uv run python main.py stage structured --sanitized-input examples/universities.json --judge-universities --output outputs/university-review.csv
```

Start the shared local server first. Qwen calls use `prompts/structured.md` and the
strict `UniversityJudgment` schema. Raw-file input cannot enable this flag while
automatic privacy preparation is unfinished. Prepared input is caller attestation.

Both fuzzy matching and Qwen return proposals with `applied: false`. Even a confident
same-institution judgment does not automatically merge names. Candidate work is capped
at 100 distinct names and 200 comparisons; reports flag truncated candidate review.
Without Qwen, string similarity is used only to identify review candidates.

## Folder and ZIP support

```bash
uv run python main.py batch-structured --input data --output-dir outputs/agent2-run
uv run python main.py batch-structured --input input.zip --output-dir outputs/agent2-zip-run
```

The batch reads the selected sheet/header from each XLSX (first sheet/row by default),
keeps each table separate, and shares observed university spellings across files.
An empty or invalid selected sheet fails the batch before output; select a valid
sheet or process heterogeneous workbooks separately. ZIPs are read in memory without
extracting archive paths. Duplicate basenames in separate folders are retained.

Choose a new output directory outside the input folder. Existing output directories
are rejected. Outputs contain numbered `.structured.xlsx` files and per-table JSON
reports under `standardized_files/`, a `structure_report.csv` mapping outputs to
sources, and `Agent2_Standardized_Output.zip` containing only standardized XLSX files.
Reports remain outside the ZIP. Only the selected table is exported, not all workbook
formatting/sheets. The batch is deterministic and does not invoke Qwen.

This replaces the PR's destructive extraction/output cleanup and silent same-name
file collisions. Existing source/output folders are never deleted by the command.
