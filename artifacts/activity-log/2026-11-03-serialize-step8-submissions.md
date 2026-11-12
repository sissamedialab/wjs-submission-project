## 2026-11-03 — Serialize step-8 submissions to stop double submits
**What:** `SubmissionStep8View.post` now locks the article row (`select_for_update` in `transaction.atomic`) before processing, and sends a late or concurrent second POST of an already submitted article to the status page with "This submission has already been completed.". The step-8 template disables the Submit button on submit and re-enables it when the page comes back from the browser cache.
**Why:** specs#3233: two overlapping POSTs of a revision (double click, slow response) raised `RevisionStorage.DoesNotExist` (500), or silently re-ran the first-submission flow (submission date overwritten, acknowledgements re-sent), or hit `TransitionNotAllowed`. The stale form save also autocommitted a stage revert, since there is no `ATOMIC_REQUESTS`.
**Decisions:** The lock lives in the view, not in `CompleteSubmission`, so the form is built from the locked, fresh row. PostgreSQL re-evaluates the queryset filter after the lock is released, so the second request gets no row and is redirected instead of failing. The "already completed" check reuses the owner/correspondence-author and journal filters, so co-authors and other journals still get 404. The button disable is a UX aid only; the lock is the real fix.
**Agent usage:**

| Stage | Agent/skill | Tokens | Time |
|---|---|---|---|
| Design | superpowers:brainstorming (builder check subagent) | ≈57k | ≈1m |
| Implementation | superpowers:executing-plans (inline) | — | — |
| Review | superpowers:requesting-code-review (final reviewer, opus) | ≈110k | ≈3m |

**Considered & dropped:** A unique "submission in progress" flag on `RevisionStorage` (needs a migration and cleanup on errors); client-side protection only (does not cover history resubmits or two tabs).
**Follow-ups:** Deferred minor M3: if the user presses Stop before any response, the button stays disabled until reload. The companion wjs-profile-project MR (race tests + `report_double_submissions` command) needs a `wjs-submission` version bump once this is released.
**Refs:** wjs/specs#3233; spec artifacts/specs/2026-11-03-step8-double-submit-design.md; plan artifacts/plans/2026-11-03-step8-double-submit.md; Eval: 76% — artifacts/evaluations/2026-11-03-step8-double-submit.md
