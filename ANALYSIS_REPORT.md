# Pipeline analysis report

## Verified run

- Date: 2026-09-13
- KAUST Ibex job: `51859090`
- Compute: one NVIDIA V100 GPU, 8 CPUs, 32 GB RAM
- Runtime: 7 minutes 55 seconds
- Result: completed with exit code 0
- Model: Qwen3.5-2B Q4_K_M (1.28 GB GGUF), served locally by CUDA llama.cpp
- Output: `/ibex/user/bahajao/Data_Cleaning_Agent/outputs/run-51859090/`

The run processed 17 nonempty sheets from 12 Excel workbooks, skipped two empty
sheets, and preserved all 2,334 input rows. It wrote 17 cleaned CSV files, 17 JSON
audit reports, and one `summary.json`. No input workbook was overwritten.

## What changed

| Stage | Recorded changes |
| --- | ---: |
| Schema | 301 |
| Structured fields | 4,591 |
| Categories | 778 |
| Text | 1,169 |
| Validation | 0 (read-only) |
| **Total** | **6,839** |

Direct identifiers were masked in memory before model requests and restored before
export. The final Q4 run had no whole-table schema fallbacks. Qwen omitted 24
individual mappings and gave 24 low-confidence mappings; those columns were kept
or conservatively named and marked for review.

## Validation findings

The final validator produced 5,521 issue entries. These are cell, column, and row
flags, not 5,521 distinct people or confirmed errors. No flagged value was deleted
or guessed.

| Leading finding | Count | Interpretation |
| --- | ---: | --- |
| Missing or placeholder text | 2,997 | Mostly empty conditional-form branches; applicability needs form context |
| Duplicate rows | 957 | Every member of a duplicate group is counted; review before deduplication |
| Numeric identifiers needing review | 598 | Excel stored IDs numerically, so lost leading zeros cannot be reconstructed safely |
| Columns containing missing values | 290 | Column-level counts; missing does not always mean invalid |
| Multi-value category cells left intact | 204 | The scalar category agent does not split lists automatically |
| Missing category mappings | 190 | Qwen did not return a safe mapping; original values remain |
| Ambiguous academic levels | 66 | Year/semester wording was not guessed |
| Invalid email flags | 44 | Requires manual inspection |
| Unknown gender labels | 40 | Original labels remain |
| Invalid or unsupported phone flags | 22 | Values that could not be safely converted to Saudi E.164 |

All 17 tables completed every pipeline stage, but none had zero review findings.
The outputs are cleaned and auditable, while final deduplication and decisions about
conditional missing values still require a human who understands each form.

## Quality conclusion

The original 2-bit quantization was not reliable enough for strict JSON: it caused
all 17 schemas to fall back. Keeping the same 2-billion-parameter Qwen model and
moving to Q4_K_M, together with 12-column schema batches and checked positional
reconciliation, reduced whole-schema fallbacks to zero and enabled semantic changes.
The deterministic stages remain responsible for high-risk structured values, and
the model cannot write files or execute code.
