# Step 8 read-only refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the step 8 files table read-only after the conversion-completed refresh, for new submissions and revisions.

**Architecture:** The step 8 table (rendered with `read_only=True`) adds `?read_only=1` to the refresh URL. `RenderSubmissionFile` honours that flag, keeping the old `current_step > 7 and not is_revision` rule as fallback.

**Tech Stack:** Django, HTMX, pytest (`tests/test_views.py`).

**Spec:** `artifacts/specs/2026-11-16-step8-readonly-refresh-design.md` (issue wjs/specs#3353)

## Global Constraints

- Step 6 behaviour unchanged (refresh without the flag renders the editable table).
- No `closeModal` listener added to step 8.
- No change to delete/upload views or URLs.
- Commit messages in English, Conventional Commits.

## Review Focus

- Refresh with flag for a revision at any `current_step`: must be read-only (test in Task 1).
- Refresh with flag for a new submission at `current_step=7`: must be read-only (Task 1).
- Refresh without flag for a new submission at `current_step=6`: must stay editable (Task 1).
- Flag values other than `1` (e.g. `0`, empty): must not make the table read-only (Task 1).
- `files_table.html` cannot be rendered in this repo's CI (needs `wjs_review` tags from wjs-profile-project): wiring is checked ad hoc in the browser at wrap-up (Task 2).

---

### Task 1: `RenderSubmissionFile` honours `read_only` query flag

**Files:**
- Modify: `wjs/plugins/wjs_submission/step6/views.py` (`RenderSubmissionFile.get_context_data`, ~line 279-292)
- Test: `tests/test_views.py`

**Interfaces:**
- Produces: `GET wjs_submission_6_render?read_only=1` → context `read_only=True`.

- [ ] **Step 1: Write failing tests** in `tests/test_views.py`, following the existing pattern of patching `render_to_response` and reading `render.call_args.args[0]` (see `test_submission_step8_shows_article_license_and_rights`). Patch target: `plugins.wjs_submission.step6.views.RenderSubmissionFile.render_to_response`. URL: `reverse("wjs_submission_6_render", kwargs={"article_id": article.pk, "file_type": "manuscript"})`; log in as `article.owner`. A parametrized test `test_render_submission_file_read_only(...)` with these cases (set `article.current_step`, optionally create a `RevisionStorage` as in `test_submission_step8_revision_without_access_mode_redirects`, GET with the given query string):
  - new submission, `current_step=7`, `?read_only=1` → `context.get("read_only")` is True
  - revision (`RevisionStorage` FULL), `?read_only=1` → True
  - new submission, `current_step=6`, no query → falsy
  - new submission, `current_step=7`, `?read_only=0` → falsy
  - new submission, `current_step=8`, no query → True (existing fallback)

- [ ] **Step 2: Run** `pytest tests/test_views.py -k render_submission_file_read_only -v`. Expected: the two `?read_only=1` cases FAIL.

- [ ] **Step 3: Implement** in `RenderSubmissionFile.get_context_data`: set `context["read_only"] = True` when `self.request.GET.get("read_only") == "1"` or the existing `current_step > 7 and not is_revision(...)` condition holds; update the docstring to describe the flag.

- [ ] **Step 4: Run** `pytest tests/test_views.py -k render_submission_file_read_only -v`. Expected: all PASS. Then `pytest tests/test_views.py -v` with no regressions.

- [ ] **Step 5: Commit** `fix: honour read_only flag when re-rendering the files table`

### Task 2: Step 8 table refreshes with the read-only flag

**Files:**
- Modify: `wjs/plugins/wjs_submission/templates/wjs_submission/step6/includes/files_table.html` (the `render_url` computation, line ~40)

**Interfaces:**
- Consumes: Task 1 (`?read_only=1` honoured).

- [ ] **Step 1: Implement**: when `read_only` is true, the refresh buttons' `hx_get` uses `render_url` with `?read_only=1` appended (both the DEBUG and the hidden `.js-refresh` variants; use `{% if read_only %}` around the URL or a `with` variable, e.g. `render_url_ro`). Delete/upload buttons unchanged.

- [ ] **Step 2: Verify** (template not renderable in CI, so no automated test): run `pre-commit run --files <changed files>` and check manually in the browser per the Playwright mode chosen at flow start: on step 8, trigger a conversion completion (or click the refresh button) and confirm no delete/upload buttons appear, for a new submission and a revision; step 6 still shows them.

- [ ] **Step 3: Commit** `fix: keep step 8 files table read-only after conversion refresh` (fold into the Task 1 commit if the commit strategy says so).

## Self-review

- Spec coverage: query flag + fallback (Task 1), template wiring (Task 2), tests for new submission/revision/step 6 (Task 1). Non-goals untouched.
- Names consistent: `read_only` query parameter and context key throughout.
