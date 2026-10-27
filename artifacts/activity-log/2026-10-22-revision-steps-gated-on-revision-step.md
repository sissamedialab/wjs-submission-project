## 2026-10-22 — Revision steps gated on the revision progress
**What:** During a revision the navigation bar now makes a step available only after the previous active step has been saved, like a first submission (wjs-help#193).
**Why:** Step availability was computed from `article.current_step`, which is 8 for any already-submitted article, so every revision step was clickable; the post-save redirect instead followed `RevisionStorage.revision_step`. Opening a later step and then saving an earlier one sent the author forward unexpectedly (the scenario behind wjs-help#190).
**Decisions:** One helper, `Step._get_last_completed_step`, now feeds both `get_steps_states` and `get_incomplete_step_url`, so navigation and redirect cannot drift apart again. Gating stays navigation-only, as in submission: direct URLs to later steps still open (user decision). The redirect's broad `except AttributeError` became an explicit `not article or not article.pk` guard.
**Agent usage:**

| Stage | Agent/skill | Tokens | Time |
|---|---|---|---|
| Design | superpowers:brainstorming (inline) | not measured | — |
| Design | superpowers:writing-plans (inline) | not measured | — |
| Implementation | superpowers:executing-plans (inline) | not measured | — |
| Review | code-reviewer subagent (Opus) | ~72k | ~1.5m |

**Considered & dropped:** Server-side enforcement of unavailable steps (would change first submissions too; kept out of scope). Resetting `article.current_step` at revision start via `REVISION_RESET_ARTICLE_CURRENT_STEP` (would lose the original submission's progress; the storage already carries a revision counter).
**Follow-ups:**
- `SubmissionLastStepRedirectView` (`views.py`) still resumes from `current_step` during revisions and lands on step 0 — separate issue.
- `get_steps_states` with an unsaved `Article` raises in `is_correction` (pre-existing; views pass `None`, so not reachable today).
- Local test environment: `SkipMigrations` lacks `setdefault`, which django-debug-toolbar 7.x calls; `pytest-freezegun` imports `distutils`, missing on Python 3.13. Both break `pytest` from `janeway/src` without workarounds.
- `tests/test_views.py::test_submission_author_only[False]` fails locally with and without this change (TypeError on a `PosixPath` while rendering a 404).
**Refs:** wjs-help#193, related wjs-help#190; spec `artifacts/specs/2026-10-22-revision-step-gating-design.md`; plan `artifacts/plans/2026-10-22-revision-step-gating.md`. Eval: 80% — artifacts/evaluations/2026-10-22-revision-step-gating.md
