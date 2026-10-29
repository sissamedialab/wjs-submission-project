# Step 3 flat-keywords validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore step 3 for journals with `hierarchical_keywords=off` while still enforcing the per-journal keyword count, ignoring weights.

**Architecture:** `HandleKeywordSelection.run` branches on `journal.submissionconfiguration.hierarchical_keywords`. Hierarchical journals keep parse → validate → persist. Flat journals skip parsing and persisting and validate the keywords `KeywordModelForm.save()` already stored on the article.

**Tech Stack:** Django, pytest (run from `janeway/src`, see `.claude/rules/tests.md`).

**Spec:** `artifacts/specs/2026-10-27-flat-keywords-step3-validation-design.md`

## Global Constraints

- Double quotes, line length 119, docstrings in imperative mood (ruff, `.claude/rules/linting.md`).
- Validators keep their signature `(keyword_weights: dict, journal, arxiv_category) -> tuple[bool, str | None]`; only the dict keys are used for flat journals.
- No template/JS change; no change to the hierarchical flow.
- Tests: bare `assert` needs a message.

## Review Focus

- Flat journal posts 0 keywords: rejected with "You must select between 1 and 3 keywords.", nothing persisted.
- Flat journal posts 4 keywords: rejected the same way, keyword save rolled back.
- Flat journal mixing checkbox and free-text keywords: both counted.
- Flat journal re-submitting step 3 (existing keywords on the article): count reflects the new selection, not the old one.
- Hierarchical journal behaviour (weights, validation errors) unchanged.

---

### Task 1: Validate flat-journal keywords by count

**Files:**
- Modify: `wjs/plugins/wjs_submission/step3/logic.py` (`HandleKeywordSelection`)
- Test: `tests/test_views.py` (around `test_keyword_handling`, line ~353)

**Interfaces:**
- Produces: `HandleKeywordSelection.get_keyword_weights(self) -> dict[int, int | None]` — hierarchical: `parse_keyword_weights()`; flat: `{pk: None for pk in article.keywords.values_list("pk", flat=True)}`. `run()` uses it, and calls `persist` only for hierarchical journals.

- [ ] **Step 1: Write the failing tests in `tests/test_views.py`**
  - Add `test_flat_journal_keyword_count_enforced` parametrized on the post data, with a non-hierarchical journal (default `article.journal`), keywords pk 1–4 created as in `test_keyword_validator_rejects_selection_outside_journal_interval`:
    - `{"keywords": ["1", "2"]}` → 302.
    - `{"keywords": ["1", "2", "3"]}` → 302.
    - `{"keywords": "1,free one"}` (checkbox word plus a free-text keyword, as the Tagit text field posts them) → 302. Confirm in the first run how the form accepts it and adjust the post shape to what `KeywordModelForm.save()` consumes.
    - `{}` → 200, error `"You must select between 1 and 3 keywords."` in `form.errors["__all__"][0]`, `article.keywords` empty.
    - `{"keywords": ["1", "2", "3", "4"]}` → 200, same error, `article.keywords` empty (rollback).
  - Add `test_flat_journal_resubmit_counts_new_selection`: post 3 keywords, then post 4; assert the second post fails and the article keeps its original state rolled back as the transaction dictates.
  - Make `test_keyword_handling` and `test_keyword_validator_rejects_selection_outside_journal_interval` request the `hierarchical_keywords` fixture: they post `keyword_<id>_weight` fields, which only the hierarchical flow reads.
  - Failure messages on every assert.

- [ ] **Step 2: Run to verify they fail**

  Run (from `janeway/src`): `pytest ../../wjs-submission-project/tests/test_views.py -k "keyword" -v`
  Expected: the new flat-journal passing cases FAIL (step 3 returns 200 with the interval error).

- [ ] **Step 3: Implement `get_keyword_weights` and branch `run()` in `step3/logic.py`**

  Check `self.article.journal.submissionconfiguration.hierarchical_keywords`. `run()`: `keyword_weights = self.get_keyword_weights()`, `self.run_validator(keyword_weights)`, `if hierarchical: self.persist(keyword_weights)`. Update the `run` docstring. Keep `parse_keyword_weights`, `run_validator` and `persist` untouched.

- [ ] **Step 4: Run to verify they pass**

  Run: `pytest ../../wjs-submission-project/tests/test_views.py ../../wjs-submission-project/tests/test_forms.py -k "keyword" -v`
  Expected: all PASS. Then the full suite `pytest --create-db -n7 ../../wjs-submission-project`; the known unrelated failures from !173 (`test_arxiv.py::test_article_creation_and_endpoint`, `test_views.py::test_submission_author_only[False]`, `test_logic.py::test_double_arxiv_id_submission[0]`) may still fail identically on `wjs-develop`.

- [ ] **Step 5: Commit** (cadence per step 4 of the flow; message `fix(step3): validate keyword count for journals without hierarchical keywords`)
