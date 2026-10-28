# Evaluation — flat-keywords-step3

- **Date:** 2026-10-27
- **Branch:** bugfix/issue-3280-flat-keywords-step3 (working tree, uncommitted)
- **Task:** specs#3280 (follow-up to MR !173)
- **Coverage:** full

## Scores
| Dimension | Score | Weight | Key evidence |
|---|---|---|---|
| Functionality | 4 | 20 | Flat journals validated by count, weights ignored (`step3/logic.py` `get_keyword_weights`/`run`); autocomplete-on/hierarchical-off path not exercised by a test |
| Testing | 4 | 15 | Red→Green seen (2 valid flat cases failed before the fix); 0/4 keywords and resubmit rejected; full suite 349 passed |
| Security | 4 | 15 | No new trust-boundary input; flat path reads only keywords already stored by the form |
| Code quality | 4 | 15 | ruff shows the same 3 pre-existing findings with and without the change; format clean |
| Maintainability | 4 | 15 | Single `hierarchical` property drives both branches; validators and `persist` untouched |
| Error handling | 4 | 10 | Failing count raises `ValidationError`, handled by the existing `form_valid`; form transaction rolls the keyword save back (tests assert empty `article.keywords`) |
| Documentation | 4 | 10 | Docstrings on new/changed methods; no prose docs reference this flow |

## Recommendations
- None required (every dimension ≥ 4).

## Total
**80%** — correct, tested fix; remaining gap is an untested autocomplete-flat variant and mixed checkbox+free-text posting.
