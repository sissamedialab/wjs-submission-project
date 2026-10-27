# Revision step gating — design

- **Date:** 2026-10-22
- **Related:** wjs-help#190 (revision submission error, dev-4220)
- **Scope:** `wjs/plugins/wjs_submission/workflow.py`, `tests/test_workflow.py`

## Problem

During a revision the author can open any step from the navigation bar, including
steps they have not reached yet. If they open a "later" step and then save an earlier
one, they are redirected forward to the latest step they reached instead of the next
step in sequence. This is the scenario behind wjs-help#190 (save step 1 → land on
step 4 → leave and come back → inconsistent state on save).

### Root cause

Navigation and post-save redirect follow two different counters:

- `Step.get_steps_states()` computes the availability of each step from
  `article.current_step`. An article under revision has already been submitted, so
  `current_step` is 8 and every active step is available.
- `Step.get_incomplete_step_url()` (the post-save redirect) already uses
  `RevisionStorage.revision_step`, the highest step saved in the current revision.

`RevisionStorage` is created when a revision starts and deleted when the revision is
completed, so `revision_step` always starts at 0 for each new revision.

## Goal

Revision steps are linked like submission steps: a step becomes available only after
the previous active step has been saved.

## Design

In `Step.get_steps_states()`, determine the "last completed step" with the same rule
as `get_incomplete_step_url()`:

- if the article has a `RevisionStorage`, use `revision_step`;
- otherwise, use `article.current_step`.

Reuse the existing `_get_incomplete_revision_step()` /
`_get_incomplete_article_step()` helpers so the two methods cannot drift apart again.
The rest of the availability rule is unchanged: a step is available if it is active
and its number is ≤ the last completed step, and the first active step after that is
also available.

When there is no article (a new submission before step 1 is saved), behaviour is
unchanged.

### Resulting behaviour

| Flow | Active steps | After start | After saving step 1 |
|------|--------------|-------------|---------------------|
| Confirm | 1, 8 | 1 | 1, 8 |
| Metadata | 1, 4, 5, 7, 8 | 1 | 1, 4 |
| Full | 1, 4, 5, 6, 7, 8 | 1 | 1, 4 |

Re-saving an earlier step redirects to the first step not yet saved, as in a first
submission. Because later steps cannot be opened from the navigation, this is always
the next step in sequence.

### Out of scope

- **Server-side enforcement.** A step that is not available can still be reached by
  typing its URL. This matches the current submission behaviour and was explicitly
  kept as is.
- The `REVISION_RESET_ARTICLE_CURRENT_STEP` setting is left untouched.
- No change to first submissions or corrections (they have no `RevisionStorage`).

## Testing

Written first in `tests/test_workflow.py`, using the existing revision fixtures:

1. For a new revision of each type (confirm, metadata, full), only step 1 is
   available, even though `article.current_step` is 8.
2. After step 1 is saved (`revision_step = 1`), the next active step becomes
   available: step 8 for confirm, step 4 for metadata and full; later steps stay
   unavailable.
3. With partial progress (e.g. full revision with `revision_step = 5`), steps 1, 4,
   5 and 6 are available; 7 and 8 are not.
4. Regression: a first submission (no `RevisionStorage`) still uses
   `article.current_step`.
