## 2026-10-27 — Step 3 works again for journals without hierarchical keywords
**What:** Step 3 now validates the keyword count of journals with `hierarchical_keywords=off` on the keywords stored by the form, ignoring weights; hierarchical journals are unchanged (specs#3280, regression from !173).
**Why:** !173 made `run_validator` raise and look validators up by journal code, but the validators read `keyword_weights`, built only from `keyword_<id>_weight` POST fields that only the hierarchical template posts. Flat journals therefore always got an empty selection and "You must select between 1 and 3 keywords.", blocking submission.
**Decisions:** Count enforced for flat journals (user decision), counting checkbox and free-text keywords together. `HandleKeywordSelection.get_keyword_weights` returns `dict.fromkeys(article.keywords pks)` for flat journals; `persist` runs only for hierarchical ones. Four existing tests that posted weights on a non-hierarchical journal now request the `hierarchical_keywords` setup.
**Agent usage:**

| Stage | Agent/skill | Tokens | Time |
|---|---|---|---|
| Design | superpowers:brainstorming (inline) | not measured | — |
| Design | superpowers:writing-plans (inline) | not measured | — |
| Implementation | inline, TDD | not measured | — |
| Review | none dispatched (code-eval self-score) | — | — |

**Considered & dropped:** Skipping validators entirely for flat journals (the pre-!173 behaviour; rejected because the count must still be enforced). Parsing weights from checkbox posts (flat journals have none).
**Follow-ups:**
- No test for `autocomplete_keywords=on` with `hierarchical_keywords=off`, nor for checkbox plus free-text posted together (the Tagit field posts a comma-separated string).
- JQuant/JHEP group rules would fail on a flat journal; they are hierarchical today.
- Pre-existing ruff findings in `step3/logic.py` (try-clause length) and `tests/test_views.py` (`noqa` style) untouched.
**Refs:** specs#3280, MR !173; spec `artifacts/specs/2026-10-27-flat-keywords-step3-validation-design.md`; plan `artifacts/plans/2026-10-27-flat-keywords-step3-validation.md`. Eval: 80% — artifacts/evaluations/2026-10-27-flat-keywords-step3.md
