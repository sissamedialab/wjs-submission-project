# Evaluation — respect-keyword-deactivated

- **Date:** 2026-09-23
- **Branch:** bugfix/issue-3053-respect-keyword-deactivated (working tree, on top of wjs-develop 07f917d)
- **Task:** [wjs/specs#3053](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3053)
- **Coverage:** full — all three changed files read in full

## Scores

| Dimension | Score | Weight | Key evidence |
|---|---|---|---|
| Functionality | 4 | 20 | 9 tests red before, `262 passed, 1 xfailed` after; both journal shapes and both arXiv branches covered. Residual, scoped-out gap: the POST-side validators still accept a deactivated keyword id (`keywords.py:150-260`). |
| Testing | 5 | 15 | 10 new tests, Red→Green captured; `tests/test_views.py:596-651` assert against rendered HTML, not context; `test_get_keywords_by_journal_prefetches_the_whole_group_tree` pins the 4-query shape so a refactor cannot silently make the fix a no-op. |
| Security | 4 | 15 | No new inputs, secrets or string-built SQL. Change strictly narrows exposure: `_with_keyword_prefetches` (`keywords.py:39-66`) also closes a pre-existing cross-journal keyword leak via `group.keywords.all`. |
| Code quality | 5 | 15 | Two single-purpose helpers replace duplicated queryset logic; `pre-commit run --all-files` clean (ruff + ruff-format); Sphinx `:param:`/`:return:` style matches the module. |
| Maintainability | 4 | 15 | Non-obvious Django constraint documented inline (`keywords.py:56-58`). Gap: the contract that any `KEYWORD_FILTERS` callable must carry these prefetches lives only inside `_with_keyword_prefetches`, not in `settings.py`'s `DEFAULT_KEYWORD_FILTERS`. |
| Error handling | 3 | 10 | No new exception paths (pure queryset code). A keyword deactivated after selection now disappears from step 3 and is dropped on the next save with no notice to the author — a deliberate consequence of the requirement, but a silent one. |
| Documentation | 4 | 10 | Docstrings on both new helpers and updated on both changed public functions, stating the deactivated rule. No README/CHANGELOG change needed (CHANGELOG is release-time only; no towncrier in this repo). |

## Recommendations

- **Error handling:** consider surfacing dropped keywords to the author (or tracking a follow-up issue), so a submission silently losing a previously-chosen keyword is a visible event rather than an invisible one.

## Total

**84%** — Correct, well-tested fix that goes past the issue's literal wording to the place the bug actually bites; the remaining gaps are scoped-out by decision or cosmetic.
