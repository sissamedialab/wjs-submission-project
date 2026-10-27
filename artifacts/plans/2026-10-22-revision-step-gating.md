# Revision Step Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** During a revision, a step is available in the navigation bar only after the previous active step has been saved, as in a first submission.

**Architecture:** `Step.get_steps_states()` and `Step.get_incomplete_step_url()` both read the "last completed step" from a single new helper, which returns `RevisionStorage.revision_step` when the article is under revision and `article.current_step` otherwise. No other module changes.

**Tech Stack:** Django (Janeway plugin), pytest + pytest-django.

**Spec:** `artifacts/specs/2026-10-22-revision-step-gating-design.md`

**Branch:** `bugfix/issue-193-revision-step-gating` (wjs-help#193)

## Global Constraints

- Change limited to `wjs/plugins/wjs_submission/workflow.py` and `tests/test_workflow.py`.
- No server-side enforcement: direct URLs to unavailable steps keep working (out of scope per spec).
- `REVISION_RESET_ARTICLE_CURRENT_STEP` is not touched.
- First submissions and corrections (no `RevisionStorage`) keep using `article.current_step`.
- Line length 119, double quotes, docstrings in imperative mood (ruff, see `.claude/rules/linting.md`).
- Tests run from `janeway/src`: `pytest ../../wjs-submission-project/tests/test_workflow.py` (see `.claude/rules/tests.md`).
- Changes stay in the working tree unless per-change commits are chosen at flow step 4.

## Review Focus

- **Unsaved or missing article** (`article is None`, or `article.pk is None` on the first step-1 render): must not query `RevisionStorage` and must behave as today (only step 1 available). Covered by existing `test_step_state_mapping`-style calls with `journal` only; add `test_steps_states_without_article_unchanged` in Task 1.
- **Revision on an article whose `current_step` is 8**: `current_step` must be ignored while a `RevisionStorage` exists. Pinned by every revision test in Task 1, which set `current_step = 8`.
- **Inactive steps between saved steps** (steps 2 and 3 are always inactive in revisions; step 6 is inactive in metadata): the "next active step" must skip them. Pinned by the parametrised cases in Task 1.
- **Post-save redirect** must keep using the same counter as the navigation: `get_incomplete_step_url()` is refactored onto the helper and pinned by `test_incomplete_step_url_uses_revision_step`.

---

### Task 1: Gate revision steps on `revision_step`

**Files:**
- Modify: `wjs/plugins/wjs_submission/workflow.py` — `Step._get_incomplete_revision_step`, `Step._get_incomplete_article_step`, `Step.get_incomplete_step_url` (around lines 64-104), `Step.get_steps_states` (around lines 131-166)
- Test: `tests/test_workflow.py`

**Interfaces:**
- Produces: `Step._get_last_completed_step(article: Article | None) -> int` (staticmethod). Returns `0` when `article` is `None` or unsaved; `RevisionStorage.revision_step` if a `RevisionStorage` exists for the article; otherwise `article.current_step`.
- `get_steps_states()` and `get_incomplete_step_url()` keep their signatures and return types.

- [ ] **Step 1: Write the failing tests** in `tests/test_workflow.py`

Add a module-level helper and four tests. Set up revisions the same way as `tests/test_views.py` does, with `RevisionStorage.objects.create(article=..., revision_flow_type=..., revision_step=...)`. Before each revision test, set `article.current_step = 8` and `article.stage = STAGE_UNDER_REVISION`, then save.

```python
def _start_revision(article, flow_type, revision_step=0) -> RevisionStorage: ...
    # article.current_step = 8; article.stage = STAGE_UNDER_REVISION; article.save()
    # return RevisionStorage.objects.create(article=article, revision_flow_type=flow_type, revision_step=revision_step)

def _available(states) -> set[int]:
    return {number for number, state in states.items() if state.available}
```

`test_revision_steps_states` — parametrised on `(flow_type, revision_step, expected)`, asserting `_available(Step.get_steps_states(article.journal, article)) == expected` with a message naming the flow and the step:

| flow_type | revision_step | expected available |
|-----------|---------------|--------------------|
| CONFIRM | 0 | `{1}` |
| CONFIRM | 1 | `{1, 8}` |
| METADATA | 0 | `{1}` |
| METADATA | 1 | `{1, 4}` |
| METADATA | 5 | `{1, 4, 5, 7}` |
| FULL | 0 | `{1}` |
| FULL | 1 | `{1, 4}` |
| FULL | 5 | `{1, 4, 5, 6}` |
| FULL | 7 | `{1, 4, 5, 6, 7, 8}` |

`test_incomplete_step_url_uses_revision_step` — FULL revision, `revision_step=4`, `current_step=8`: `STEPS[1].get_incomplete_step_url(article) == reverse("wjs_submission_5", kwargs={"article_id": article.pk})`. This already passes and guards the refactor.

`test_steps_states_without_article_unchanged` — `Step.get_steps_states(journal)` (no article): `_available(states) == {1}`.

`test_submission_ignores_missing_revision_storage` — no `RevisionStorage`, `article.current_step = 4`: `_available(states) == {1, 3, 4, 5}` with step 2 patched inactive as in `test_step_state_mapping_skipped_step_no_lookahead_drift`. Confirms first submissions still use `current_step`; this already passes too.

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `janeway/src`): `pytest ../../wjs-submission-project/tests/test_workflow.py -k "revision or without_article or missing_revision" -v`
Expected: `test_revision_steps_states` FAILS for every case, because all active steps are available (`current_step=8`). The other three PASS.

- [ ] **Step 3: Implement `Step._get_last_completed_step(article: Article | None) -> int`** in `workflow.py`

Add it as a staticmethod that replaces `_get_incomplete_revision_step` and `_get_incomplete_article_step`, and delete those two methods. Return `0` for `None` or an unsaved article (`not article.pk`). Read the storage with `RevisionStorage.objects.filter(article=article).values_list("revision_step", flat=True).first()`: that is one query, with no exception handling. Fall back to `article.current_step` when the value is `None`.

Then:
- `get_incomplete_step_url()`: `next_step = max(self._get_last_completed_step(article), self.step_number) + 1`. Keep the `AttributeError` fallback to `reverse("wjs_submission_1")`.
- `get_steps_states()`: compute `last_completed = cls._get_last_completed_step(article)` once before the loop, and use `available = active and step.step_number <= last_completed`. The `article and` guard is no longer needed because the helper returns `0`. Update the docstring: "less than or equal to the last completed step (the revision step during a revision, the article current step otherwise)".

- [ ] **Step 4: Run the whole workflow test module**

Run: `pytest ../../wjs-submission-project/tests/test_workflow.py -v`
Expected: all PASS, including the existing `test_step_state_mapping*` tests (regression for first submissions).

- [ ] **Step 5: Run the full suite and lint**

Run: `pytest --create-db -n7 ../../wjs-submission-project` → all PASS.
Run (from the repo): `pre-commit run --all-files` → all hooks pass.

- [ ] **Step 6: Commit (only if per-change commits were chosen at flow step 4)**

```bash
git add wjs/plugins/wjs_submission/workflow.py tests/test_workflow.py
git commit -m "fix(revision): make revision steps available only after the previous one is saved"
```
