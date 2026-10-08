# Errata / Addenda: arXiv category on the article page — design

> **Update 2026-10-07 (MR !166 review):** the backfill (section 2 / Task 2) was dropped —
> there are no live errata/addenda in production, so there is nothing to backfill. Only the
> copy at creation time ships.

- **Issue:** wjs/specs#3212 — "Errata / Addenda should have arXiv category on article page"
- **Journal:** JCAP (fix is journal-agnostic)
- **Date:** 2026-10-06

## Problem

On the article page (`wjs_article_details`, `status/<pk>/`) the metadata section renders
the arXiv identifier followed by the arXiv category in brackets
(`wjs_review/details/elements/metadata_main.html`, in wjs-profile-project):

```
<arXiv id link>  ({{ article.submission_data.arxiv_category }})
```

For errata and addenda the brackets are empty. The two values come from different places:

- the **id** comes from `article.identifiers` (`id_type="arxiv"`), which
  `SetupCorrectionStorage._get_or_create_correction_article()` copies from the
  corrected article;
- the **category** comes from `ArticleSubmission.arxiv_category`, which is normally set
  by the arXiv submission step (`arxiv.py`). Corrections skip that step, and
  `SetupCorrectionStorage._populate_metadata()` creates an empty `ArticleSubmission`
  without copying the category.

Requested by the EO (comment on #3212): "For errata and addenda, pls add arxiv category in
brackets, next to the arXiv id".

## Goals

1. New errata/addenda inherit the arXiv category of the corrected article.
2. Existing errata/addenda get their missing category filled in.

## Non-goals

- No template change: the page already renders the category.
- No change to how the arXiv id is copied.
- No new UI to edit the category of a correction.

## Design

### 1. Copy the category on creation

In `SetupCorrectionStorage._populate_metadata()`
(`wjs/plugins/wjs_submission/correction/logic.py`), after the correction's
`ArticleSubmission` is obtained, set its `arxiv_category` to the corrected article's
`submission_data.arxiv_category` and save.

If the corrected article has no `ArticleSubmission` (e.g. legacy/imported data), the
category stays empty: no error.

Copying at creation time matches how the arXiv id and other metadata are already
handled by `_populate_metadata()`. Reading the category through the Hydra link at render
time was considered and rejected: it would put correction-specific logic in a shared
template/model method and diverge from the existing "snapshot at creation" pattern.

### 2. Backfill existing corrections (data migration)

New migration `wjs_submission/migrations/0024_<name>.py` with a `RunPython` forward
function and `RunPython.noop` reverse.

The forward function:

- iterates Hydra `LinkedArticle` rows with `relationship` in `("erratum", "addendum")`;
- for each, takes the correction's (`to_article`) `ArticleSubmission`;
  - if missing → skip (do not create one);
  - if its `arxiv_category` is non-empty → skip (never overwrite);
- takes the corrected article's (`from_article`) `ArticleSubmission`;
  - if missing or its `arxiv_category` is empty → skip;
- otherwise copies the category onto the correction and saves.

It uses historical models (`apps.get_model`) and declares a dependency on
`("hydra", "0001_initial")` — an ordering constraint only, no hydra change — so `LinkedArticle`
(with `from_article`, `to_article`, `relationship`, the only fields read) is available.
Hydra is a mandatory plugin (unguarded imports in `correction/logic.py` loaded by the plugin
URLconf; same hard dependency already in `jcom_profile.0042_genealogy_to_hydra`), so the
dependency is unconditional; the `ImportError` guards elsewhere are leftovers. It is idempotent: re-running it changes
nothing.

The function body lives in a plain module-level function taking `apps` (pattern already
used by `0008_define_access_mode` with `plugins.wjs_submission.data`), so it can be
unit-tested directly with the real app registry.

## Testing

In `tests/test_correction.py`:

- a new erratum and a new addendum inherit `arxiv_category` from the corrected article;
- a corrected article without `ArticleSubmission` does not break correction setup and
  leaves the category empty.

For the backfill function:

- an existing correction with empty category gets the corrected article's category;
- a correction with an already-set category is left unchanged;
- a correction without `ArticleSubmission` is skipped (no row created);
- a corrected article with empty category leaves the correction unchanged.

## Scope

Single repository: wjs-submission-project. Estimated ~2h.
