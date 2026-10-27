# Evaluation — revision-step-gating

- **Date:** 2026-10-22
- **Branch:** bugfix/issue-193-revision-step-gating (working tree vs d023da6)
- **Task:** wjs-help#193
- **Coverage:** full (`workflow.py`, `tests/test_workflow.py`; spec and plan read)

## Scores
| Dimension | Score | Weight | Key evidence |
|---|---|---|---|
| Functionality | 4 | 20 | `workflow.py:150-158` gates on `_get_last_completed_step`; 9-case revision table passes; the "resume" redirect (`views.py:75-85`) still uses `current_step` during revisions — pre-existing, out of spec |
| Testing | 4 | 15 | 7/9 revision cases RED→GREEN, guard test RED→GREEN, suite 301/302 (1 pre-existing failure); nav rendering not exercised at view level |
| Security | 4 | 15 | Single ORM `filter().values_list().first()` (`workflow.py:79`), no new input handling; direct-URL access unchanged by explicit spec decision |
| Code quality | 4 | 15 | ruff + ruff-format pass; two helpers replaced by one; test reaches a private helper (`# noqa: SLF001`) |
| Maintainability | 4 | 15 | Navigation and redirect share one counter source (`workflow.py:64-82`, `:93-95`); duplicates the `RevisionStorage` lookup already done in `mixins.py:111` |
| Error handling | 4 | 10 | Broad `except AttributeError` replaced by explicit `not article or not article.pk` guard (`workflow.py:93`); no silent paths added |
| Documentation | 4 | 10 | Docstrings for the new helper and `get_steps_states` updated; spec and plan in `artifacts/`; CHANGELOG generated at release time |

## Total
**80%** — Root cause fixed in one shared helper with RED→GREEN evidence; remaining gaps are pre-existing or out of scope.
