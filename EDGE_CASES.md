# Edge-case review

Final audit of KAUST GPU job `51894880` using commit `592a616`.

- 17 tables processed successfully
- 1,369 records exported
- 0 failed tables
- 961 padding or embedded-header rows removed
- 0 missing schema mappings
- 0 failed model batches

## Confirmed clean

| Check | Remaining |
|---|---:|
| Blank rows | 0 |
| False/Absent-only padding | 0 |
| Exact duplicate rows | 0 |
| Surrounding whitespace | 0 |
| Noncanonical gender labels | 0 |
| Ambiguous academic levels | 0 |
| University equivalence warnings | 0 |

## Cases requiring human review

These values remain unchanged because an automatic correction could corrupt participant data.

| Edge case | Cells | Files | Recommended review |
|---|---:|---:|---|
| Numeric IDs imported by Excel | 598 | 6 | Check whether the original IDs contained leading zeros. |
| Unresolved items in multi-value categories | 23 | 2 | Review the individual skills and roles. |
| Category values omitted by Qwen after individual retry | 20 | 7 | Review and add approved aliases to the knowledge base. |
| Invalid email format | 18 | 11 | Correct from the source record or leave flagged. |
| Invalid phone format | 18 | 9 | Correct from the source record or leave flagged. |
| Invalid university ID | 7 | 4 | Verify against the original university record. |
| Unsupported category value or compound | 6 | 5 | Review entries such as `4.9`, `2210992`, and compound majors. |
| Low-confidence category value | 5 | 2 | Approve a canonical mapping before changing it. |
| Ambiguous timestamp | 3 | 1 | Confirm the intended date order and format. |

Detailed reports are generated locally under `outputs/validation-51894880/`. They are excluded from Git because they may correspond to private participant records.
