# Step 3: enforce keyword count for journals without hierarchical keywords

Date: 2026-10-27. Language: English (confirmed).

## Problem

MR !173 (`a11f6f4`, `fix(step3): enforce the per-journal keyword validators`) made
`HandleKeywordSelection.run_validator` raise and look validators up by `journal.code`. The validators
receive `keyword_weights`, which `parse_keyword_weights` builds only from `keyword_<id>_weight` POST fields.

Only the hierarchical template branch posts those fields. With `hierarchical_keywords=off` the template posts
plain `keywords` checkboxes plus the free-text field; `KeywordModelForm.save()` stores them without weights.
`keyword_weights` is therefore `{}` and every validator fails (JCOM/JCOMAL: "You must select between 1 and 3
keywords."), so submission cannot get past step 3 for these journals.

## Goals

- Step 3 works again for journals with `hierarchical_keywords=off`.
- The per-journal keyword count is still enforced there, counting checkbox and free-text keywords together;
  weights are ignored.

## Non-goals

- No change to the hierarchical flow, template or JS.
- No change to JQuant/JHEP group rules (those journals are hierarchical).

## Design

Change confined to `wjs/plugins/wjs_submission/step3/logic.py`, `HandleKeywordSelection`:

- Hierarchical journals: unchanged (parse weights, validate, persist).
- Non-hierarchical journals: `run()` does not parse weights and does not call `persist`. The validator input is
  built from the keywords already stored on the article by `KeywordModelForm.save()` (same transaction):
  `{keyword_pk: None for each article keyword}` — only the keys are used by the validators.
- A failing validator raises `ValidationError`; `SubmissionStep3View.form_valid` re-renders the form and the
  atomic block in `SubmissionStep3Form.save()` rolls the keyword save back.
- `autocomplete_keywords` on / `hierarchical_keywords` off takes the same flat path (keywords stored by the form).

## Tests (red first, `tests/test_views.py`)

- Flat journal, 1–3 keywords (checkboxes and/or free text): step 3 passes, `KeywordArticle` rows created by the
  form, no weights required.
- Flat journal, 0 keywords and 4 keywords: rejected with the interval error, nothing persisted.
- Existing hierarchical tests unchanged and green.
