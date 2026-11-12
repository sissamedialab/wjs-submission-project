# Evaluation — mr187-review-fixes

- **Date:** 2026-11-11
- **Branch:** feature/issue-3330-required-labels-help-text (a4f9de2..970b4d9, 3 commits: f4b438b, 53949e8, 970b4d9)
- **Task:** issue 3330 / MR 187 review threads (no plan or spec: the four review threads are the requirements)
- **Coverage:** full (5 files: `helpers/forms.py`, `step1/forms.py`, `step4/article_form.html`, `tests/test_dynamic_fields.py`, `tests/test_required_markers.py`); no browser run (e2e skipped by choice)

## Scores
| Dimension | Score | Weight | Key evidence |
|---|---|---|---|
| Functionality | 4 | 20 | All four threads addressed (threads 1–3 changed, 4 already fixed by a4f9de2); full suite 386 passed; `js_required` effect on `detect_required.js` and the blank select not exercised in a browser |
| Testing | 4 | 15 | Red→Green seen for each change (2 failures for thread 1, 4 for thread 2, 1 for thread 3); no test submits a required field of an unsupported kind through `clean()` — the case my first version would have broken |
| Security | 4 | 15 | No new input surface; log line uses `%r` args, no secrets; pre-existing `mark_safe` in `required_help_text` untouched |
| Code quality | 4 | 15 | Pre-commit (ruff, ruff-format) passed on each commit; blank select label `"---------"` is not translatable (`helpers/forms.py:71`) |
| Maintainability | 3 | 15 | `if element.kind == "textarea"` special case in `map_dynamic_field` bypasses the `FieldSpec` table that drives per-kind behaviour; `_additional_fields` is now a list, no longer a QuerySet |
| Error handling | 4 | 10 | Unsupported kind raises `KeyError` instead of returning `None`; warning names field, pk and kind; logs on every form instantiation (noisy) |
| Documentation | 4 | 10 | Typed docstrings updated for `map_dynamic_field` (incl. `:raises:`) and new `_supported_additional_fields`; no CHANGELOG entry yet (project has `CHANGELOG.md`, no `changes/`) |

## Recommendations
- Maintainability: move the `js_required` rule into `FieldSpec` (a flag set on the `textarea` entry) so `map_dynamic_field` has no per-kind branch.

## Total
**77%** — all review asks met and green; one per-kind special case outside the spec table and no browser verification are what is left.
