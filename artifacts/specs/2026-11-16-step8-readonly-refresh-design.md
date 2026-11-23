# Step 8 files table stays read-only after conversion refresh — design

Issue: wjs/specs#3353 ("uploading file in step 8 works not so well"). Language: English.

## Intent and why

In step 8 (final review) the manuscript files table is meant to be read-only. When the PDF
conversion finishes while the author is already on step 8, the table is re-fetched and comes back
editable (delete/upload buttons). Using them then leaves the upload modal open, because step 8 has
no `closeModal` listener. Step 8 should never offer these actions.

## Root cause

- `step8/article_form.html` includes `step6/includes/files_table.html` with `read_only=True`.
- On conversion `completed`, `conversion_websocket.js` clicks `.js-refresh`, which GETs
  `RenderSubmissionFile` (`step6/views.py`).
- That view sets `read_only` only if `current_step > 7 and not is_revision(article)`.
  `current_step` reaches 8 only when step 8 is saved, so it is 7 while the author views step 8;
  for revisions the condition is never true. The refreshed table is therefore editable.

## Goals

- The step 8 table remains read-only after a conversion refresh, for new submissions and revisions.
- Step 6 behaviour unchanged.

## Non-goals / anti-goals

- No `closeModal` listener in step 8 (would legitimise an unintended editable state).
- No hardening of delete/upload URLs against direct POST (already true today, out of scope).
- Do not infer read-only from the `HX-Current-URL` header.

## Approaches

- **A (chosen):** the step 8 table passes an explicit flag on the refresh URL (`?read_only=1`);
  `RenderSubmissionFile` honours it. The old `current_step > 7` heuristic stays as fallback when
  no flag is given.
- B: add a `closeModal` listener to step 8. Hides the symptom, keeps the editable state. Rejected.
- C: derive from `HX-Current-URL`. Fragile. Rejected.

## Design

- `files_table.html`: when `read_only` is true, append `?read_only=1` to `render_url`
  used by the refresh button (both DEBUG and hidden variants).
- `RenderSubmissionFile.get_context_data`: `read_only = request.GET.get("read_only") == "1"`
  or the existing `current_step > 7 and not is_revision` condition.
- Test (`tests/test_views.py`): refresh render with the flag has no delete button for
  (a) a new submission at `current_step=7`, (b) a revision; without the flag step 6 still shows it.

## Left to the builder

Exact query-param handling and test fixtures; follow existing patterns in `tests/test_views.py`.
