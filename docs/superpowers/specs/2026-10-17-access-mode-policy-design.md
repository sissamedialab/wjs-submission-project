# Access mode / licence / rights policy — design

Date: 2026-10-17
Scope: `wjs-submission-project` (with one existing hook in `wjs-profile-project`)
Related: wjs/specs#3204 (free to read errata), wjs/specs#3248 (do not change access when author/affiliation unchanged),
MR wjs-submission-project!167, wiki `Submission2025/ErratumAddendum`.

## Intent

Access mode, licence and rights are decided by a handful of simple rules. Today those rules are scattered
over the step 7 form, the step 7 view, the step 8 view and `access_mode.py`, and the step 7 form also writes
licence and rights even though the model already derives them from the access mode. Each new rule (corrections,
revisions) was added as a special case in the form, which made it hard to reason about and caused regressions
(normal open-access articles treated as corrections; author choice not applying licence/rights).

Goal: one place that knows the rules, and consumers (form, views) that do not.

## The rules

| Flow | Access mode | Licence and rights |
|---|---|---|
| Plain submission | Result of the journal control function (`ACCESS_MODE_CONTROL_FUNCTION`): fixed, or chosen by the author when the configuration allows it | Follow from the stored access mode (model sync) |
| Revision, corresponding author **and** affiliation unchanged | Kept as stored on the article, not selectable | Kept (not recalculated, including EO changes) |
| Revision, corresponding author **or** affiliation changed | As plain submission | Follow the new access mode (as plain submission) |
| Correction (erratum/addendum) | `SUBMISSION_CORRECTION_ACCESS_MODE_CODE` for the journal: `free-to-read` for JCAP/JSTAT/JINST, `open-access` for all other journals. Set when the correction is created, not selectable | Always those of the original article |

Corrections cannot change authors, so the revision "unless" clause never applies to them.

## Goals / non-goals / anti-goals

Goals
- A single policy function returns the access mode configuration for any article and flow.
- Step 7 form and view contain no knowledge of corrections or revisions rules.
- Step 8 shows exactly what will apply.
- The rules are documented in one table (wiki) and tested in one table-driven test.

Non-goals
- Rewriting `correction/logic.py` with the `revision/logic.py` pattern (planned for a later stage).
- Changing the access mode presets, the control functions, or the `setup_access_mode` data.
- Letting authors enter a custom licence/rights (they use the special request to the EO).

Anti-goals (would make this a failure)
- Any regression for plain submissions: author choice must apply the chosen mode's licence and rights.
- A normal open-access article (e.g. JCOM) being treated as a correction because its mode equals the correction mode.

## Design

### 1. Policy: `access_mode.get_access_mode_configuration(user, article)`

The only function that applies the rules, in this order:

1. Article is a correction (`workflow.is_correction`): return a fixed configuration built from the article
   (`get_article_access_mode_configuration`): access mode, licence, rights of the article, `user_can_select_access_mode=False`.
   The access mode was set at setup from `SUBMISSION_CORRECTION_ACCESS_MODE_CODE`; licence/rights are the original's.
2. Article is being revised and `is_revision_access_settings_unchanged(article)` (stored correspondence author and
   affiliation in the revision storage equal the article's, and the article has an access mode): same fixed
   configuration from the article.
3. Otherwise: result of the journal control function, unchanged.

`get_correction_access_mode_configuration` is removed (step 7 view no longer needs it);
`get_article_access_mode_configuration` stays as a helper. `get_correction_access_mode(journal)` stays (used at correction setup).

### 2. Step 7 form (`SubmissionStep7Form`, `RevisionStep7Form`, `CorrectionStep7Form`)

- Revert `step7/forms.py` to the shape of `origin/wjs-develop`, then **remove the `license` and `rights` fields** from the form
  (declared fields and `Meta.fields`). The form only handles `access_mode` and `special_request`.
- A configuration with `user_can_select_access_mode=True` offers the selectable access modes; otherwise the access mode is
  forced to the configuration's one (existing behaviour of `_inject_configuration_values`/`_setup_fields`, minus licence/rights).
- No `_keep_article_values`, no `_original_*`, no `_is_correction_configuration`, no override-flag handling, no
  seeding of `initial` from override flags, no restore on save.
- `configuration=None` (journal without access modes): the form has no licence/rights fields, so nothing is wiped.
- `CorrectionStep7Form` keeps disabling the access mode (and no longer needs to disable licence/rights fields that do not exist).

### 3. Step 7 view

`get_object` calls `get_access_mode_configuration(request.user, obj)` for every flow. The `is_correction` branch and the
`correction_parent` / `get_configuration(...)` code are removed. The confirmation text (`access_mode_confirmation_text`,
which reads `view.access_mode_configuration`) keeps working because the configuration describes the values that will apply.

### 4. How licence and rights follow (unchanged mechanisms)

- `ArticleSubmission.save()` syncs licence/rights from the journal preset of the stored access mode unless
  `license_override` / `rights_override` are set. This is the only place licence/rights are derived.
- Corrections: `SetupCorrectionStorage._populate_metadata` copies licence/rights from the original and sets both override
  flags (already implemented).
- Revisions: `PopulateRevisionStep7` (`wjs-profile-project`) clears both flags when the revision changes the stored access mode,
  so the new mode's presets apply (already implemented). If the mode is unchanged, the stored licence/rights stay.

### 5. Step 8

One helper in `access_mode.py`, `get_effective_access_settings(article) -> (access_mode, licence, rights)`. It takes only the
article (no user): it never recomputes the policy, it reads what step 7 already persisted.
- The access mode is read from where step 7 saves it: `revisionstorage.data["access_mode"]` while the article is being
  revised (full/metadata/confirm, this is what step 8 already does today), otherwise `submission_data.access_mode`.
- Licence and rights are the values stored on the article. The only exception is a revision whose stored access mode differs
  from `submission_data.access_mode`: the new mode is not applied to the article until the revision is submitted, so the
  helper returns the presets of the new mode, unless the corresponding override flag is set (then the article value).
  This mirrors what `PopulateRevisionStep7` will do at submission (it clears the flags when the mode changes), so the
  flags are ignored in that case: a changed mode always shows the new presets.

`step8/views.py` uses it and `_get_license_and_rights` is removed. The template keeps showing `article_license`/`article_rights`.

### 6. What stays / what goes

Stays: step 5 form (do not touch licence/rights of corrections, restore after `handle_defaults`), `correction/logic.py`,
`revision/logic.py`, `settings.py` correction setting, `is_revision_access_settings_unchanged`, `wjs-profile-project`
changes (`setup_access_mode`, `PopulateRevisionStep7`), the debug line in `nav.html`.

Goes: step 7 form/view special cases (above), `get_correction_access_mode_configuration`, `_get_license_and_rights` in step 8.

### 7. Tests

- One table-driven test of `get_access_mode_configuration`: rows journal (JHEP, JQuant, JCAP, JSTAT, JINST, JCOM, JCOMAL) x flow
  (plain, revision unchanged, revision changed, correction) asserting access mode, selectability and licence/rights source.
- Form tests reduced to: fixed configuration forces the mode, selectable configuration lists selectable modes, no wipe with
  `configuration=None`, author choice applies the chosen mode's licence/rights on save, a normal open-access article is not
  treated as a correction.
- Keep: step 5 correction test, step 8 effective-settings test (adapted), `PopulateRevisionStep7` override test.
- Remove tests that exist only for the removed special cases.

### 8. Documentation

Wiki `Submission2025/ErratumAddendum`: replace "Behavior" and "Relation with revisions" with the rules table above and
keep the per-journal combinations table. Mention that corrections use the journal correction access mode setting.

## Clarifications

- Starting point: the uncommitted edits in `step7/forms.py` and `tests/test_forms.py` (the "keep article values on corrections only"
  fix from the MR review) are superseded by this design and are discarded. `step7/forms.py` is reduced by hand-editing it back
  to its `origin/wjs-develop` content (`git checkout origin/wjs-develop -- <file>` is fine for that file, which only differs
  from develop by this work) and then removing the `license`/`rights` fields.
- Articles that are neither corrections nor revisions (plain submission, resubmission, draft re-entering step 7) always go
  through the control function (rule 3), whether or not they already have a stored access mode.
- A revision without a stored access mode on the article has nothing to preserve and falls through to the control function.
  If there is no `RevisionStorage` the article is not a revision, so the revision rules do not apply.
- `is_revision_access_settings_unchanged` applies to all revision types (`is_revision`: full, metadata, confirm). For types where
  author and affiliation cannot be edited the stored values equal the article's, so "unchanged" is the normal outcome.
  The table-driven test has a row per revision type for "unchanged".
- Setting: `SUBMISSION_CORRECTION_ACCESS_MODE_CODE` is the Django setting (provided by `wjs-profile-project`), read into the
  module constant `CORRECTION_ACCESS_MODE_CODE`. The tests patch that constant with an explicit dict
  (`{None: "open-access", "JCAP"/"JSTAT"/"JINST": "free-to-read"}`) and create the access modes they need; rows only cover journals
  for which test fixtures exist, the rest is covered by the `None` default.
- `workflow.is_correction` decides through Hydra: a `LinkedArticle` of type CROSSREF_UPDATES plus a section Erratum/Addendum.
  Tests either create that link or patch `is_correction` where the module imports it.

## Constraints

- Journal behaviour for plain submissions must not change (control functions untouched).
- The `wjs-profile-project` setup (`setup_access_mode`) must have been run so `free-to-read` exists for JCAP/JSTAT/JINST
  and is not user selectable.
- Existing data is not migrated; articles already affected keep their current values.

## Left to the builder

- Exact names/signatures of the Step 8 helper, as long as step 8 and the policy share the same rules.
- How to structure the table-driven test (fixtures, parametrisation).
- Whether to inline `is_revision_access_settings_unchanged` into the policy function.

## Calls made while designing (to be confirmed)

- Removing licence/rights from the step 7 form is a behaviour decision: they were hidden inputs, so authors could not enter
  custom values anyway. If a custom licence/rights input is ever needed, it is a new feature.
- Revision "unchanged" means stored correspondence author and affiliation equal the article's (same test as already implemented).
- Step 8 helper takes only the article and reads the persisted revision storage, it does not recompute the policy.
- The uncommitted WIP from the MR review fix is discarded, not reshaped.
