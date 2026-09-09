# Role instructions

Python loads Markdown as a system message and supplies JSON data separately.
One local Qwen server serves all roles. Editing Markdown does not implement tools.

| File | Runtime use |
| --- | --- |
| `schema.md` | Loaded by schema inference |
| `categories.md` | Loaded by category inference |
| `text.md` | Contract for deterministic text cleanup |
| `structured.md` | Deterministic rules contract and optional Qwen university review |
| `validation.md` | Draft for an unfinished stage |

Schema/category instructions retain the team's reasoning rules and examples.
Schema also covers conditional branches observed in the workbooks. Keep response
contracts and Python enforcement aligned with prompt changes. Do not promise an
unimplemented capability in a prompt or mark a draft stage completed.
