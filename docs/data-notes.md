# Dataset findings

Read-only inspection on 2026-09-09 covered 12 local XLSX workbooks and 19 sheets.
Only layout and aggregate findings are recorded here. Applicant values are not
committed; workbooks remain untouched in ignored `data/`.

## Layouts

- Workshop tables generally have 8–14 columns; application/team forms have 50, 56, and 59.
- One career-workshop workbook has six sheets, some with generic `Column1` headers.
- Two digital-governance exports each include an empty extra sheet.
- Two export pairs have identical loaded cell values: digital governance and
  distraction workshop. This is value equality, not byte-for-byte file comparison.

## Cases to preserve

| Observation | Required treatment |
| --- | --- |
| Participants sheet: 990 populated rows, 944 containing only booleans | Flag candidate template rows; do not count them automatically as people or delete them |
| Conditional questions populated in separate groups | Missing may mean not applicable; do not impute automatically |
| Repeated labels with numeric suffixes | Preserve branch context; suffixes do not prove another person |
| Personal and university email | Keep separate canonical fields |
| Arabic and English names | Keep separate fields |
| Generic headers or unexpected label over a timestamp | Use explicit header selection and contextual evidence |
| Numeric and string phone values | Preserve raw storage; do not invent lost digits |
| Excel dates mixed with timestamp text | Require explicit conversion policies |
| Boolean attendance and multiple day columns | Preserve false and event/day meaning |
| Identical export pairs | Separate duplicate-file checks from repeated participants |

## Coverage

Synthetic tests cover mixed headers, checkbox-only rows, Arabic text, distinct
emails, blank columns, leading-zero strings, and positional mappings. They do not
validate the real datasets. Automatic header discovery, branch applicability,
duplicate-file detection, participant reconciliation, and final validation remain
future work. The loader retains rows and supports explicit sheet/header selection.
