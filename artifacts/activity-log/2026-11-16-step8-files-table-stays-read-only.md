## 2026-11-16 — Step 8 files table stays read-only after the conversion refresh
**What:** The hidden refresh button of the step 8 files table now requests `?read_only=1`, and `RenderSubmissionFile` honours it, keeping the old `current_step > 7 and not is_revision` rule as fallback (specs#3353).
**Why:** When the PDF conversion finished while the author was already on step 8, the websocket JS clicked `.js-refresh`; the re-rendered table was editable because `current_step` is still 7 on step 8 and revisions never matched the rule. The author then saw delete/upload, and the upload modal never closed (the `closeModal` listener only exists in step 6).
**Decisions:** Fix the cause (table must stay read-only) instead of adding a `closeModal` listener to step 8. Flag passed as a query string via `render_url|add:"?read_only=1"` rather than `hx_vals` (JSON quoting through `bootstrap_button` could not be verified; reviewer suggestion). No towncrier in this repo, CHANGELOG is built at release.
**Agent usage:**

| Stage | Agent/skill | Tokens | Time |
|---|---|---|---|
| Design | superpowers:brainstorming (inline) | not measured | — |
| Design | superpowers:writing-plans (inline) | not measured | — |
| Implementation | inline, TDD (native) | not measured | — |
| Review | general-purpose reviewer subagent | ≈72k | ≈40 s |

**Considered & dropped:** `closeModal` listener in step 8 (hides the symptom, keeps the editable state); deriving read-only from `HX-Current-URL` (fragile).
**Follow-ups:**
- Template wiring is not covered by an automated test (needs `wjs_review` tags absent in this repo's CI); Playwright was skipped by choice, so it was not checked in a browser.
- Delete/upload URLs remain reachable by direct POST from step 8 (pre-existing, out of scope).
- `.js-refresh` sits inside the per-file loop, so an empty table has no refresh button (pre-existing).
**Refs:** specs#3353; spec `artifacts/specs/2026-11-16-step8-readonly-refresh-design.md`; plan `artifacts/plans/2026-11-16-step8-readonly-refresh.md`. Eval: 70% — artifacts/evaluations/2026-11-16-step8-readonly-refresh.md
