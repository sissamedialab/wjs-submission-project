# Evaluation — dynamic-field-mapping-required-labels

- **Date:** 2026-10-27
- **Branch:** bugfix/issue-3280-flat-keywords-step3 (working tree, uncommitted; not part of specs#3280)
- **Task:** —
- **Coverage:** full (13 modified files here incl. `static/js/keywords.js`, plus `tests/test_dynamic_fields.py` and `tests/test_required_markers.py`; and a one-line change in the sibling `wjs-themes` repo, `_submission-keywords.scss`), judged against `artifacts/specs/2026-10-27-dynamic-fields-required-labels-design.md` and its plan

## Scores
| Dimension | Score | Weight | Key evidence |
|---|---|---|---|
| Functionality | 4 | 20 | Spec goals met: six kinds via `FIELD_SPECS`, `kind__in` filter in `step1/forms.py`, `placeholder=""` in steps 1/4/5/6/7, markers conditional or unconditional as specced, `rows=4` in both funding forms, `data-modal-size="lg"` kept; 29 new tests pass; step 3 weights marker toggled with the weights (checked live, no JS test) |
| Testing | 4 | 15 | `test_dynamic_fields.py` + `test_required_markers.py`: 29 passed (suite 378); asserts name the behaviour; the `keywords.js` show/hide has no automated test; step 1, step 4 markers and placeholder suppression are not asserted |
| Security | 4 | 15 | No new input surface; pre-existing `mark_safe` for help text untouched |
| Code quality | 3 | 15 | `FieldSpec.help_text_as_placeholder` is set by no table entry and no test (`helpers/forms.py:37,50,55`); stale "copied from submission.forms.ArticleInfo" comment (`step1/forms.py:148`); `pre-commit run --all-files` clean |
| Maintainability | 4 | 15 | One table drives all kinds; unsupported kinds filtered once in `_additional_fields` |
| Error handling | 4 | 10 | A kind with no spec cannot reach `self.fields` (`test_step1_form_ignores_elements_of_unsupported_kind`) |
| Documentation | 4 | 10 | Typed docstrings on `FieldSpec`, `build`, `map_dynamic_field`; spec and plan present |

## Recommendations
- Code quality: remove `help_text_as_placeholder` (and its branches in `build`) or add a table entry and test that use it; refresh the stale comment above the additional-fields loop.

## Total
**77%** — complete against its spec and green; the unused `FieldSpec` option is the one cleanup left.
