# Access mode policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every access mode / licence / rights rule into `access_mode.get_access_mode_configuration` and make the step 7 form, step 7 view and step 8 view free of flow-specific special cases.

**Architecture:** The policy function returns a fixed configuration from the article for corrections and for revisions with unchanged corresponding author and affiliation, and the control function result otherwise. The step 7 form only handles `access_mode` and `special_request` (no licence/rights fields): licence and rights follow from the stored access mode through the existing `ArticleSubmission.save()` sync and its override flags. Step 8 reads what step 7 persisted through one helper.

**Tech Stack:** Django, pytest (run from `janeway/src`: `pytest ../../wjs-submission-project/tests/...`).

**Spec:** `docs/superpowers/specs/2026-10-17-access-mode-policy-design.md`

## Global Constraints

- Work in `wjs-submission-project` on branch `feature/issue-3204-free-to-read-errata` (MR !167); do not change `wjs-profile-project`.
- Plain submission behaviour must not change; control functions in `access_mode.py` are untouched.
- Correction access mode comes from `SUBMISSION_CORRECTION_ACCESS_MODE_CODE` (module constant `CORRECTION_ACCESS_MODE_CODE`): `free-to-read` for JCAP/JSTAT/JINST, `open-access` otherwise; corrections always keep the original licence and rights.
- Keep: step 5 form changes, `correction/logic.py`, `revision/logic.py`, `nav.html` debug line, `is_revision_access_settings_unchanged`.
- The uncommitted working-tree edits of `step7/forms.py` and `tests/test_forms.py` are discarded (superseded).
- Do not touch `ArticleSubmission.save()`/`_sync_access_mode_parameters` or the override flag semantics.

## Review Focus

- Journal with no access mode configuration (`get_access_mode_configuration` returns `None`): step 7 must still save without wiping licence/rights (Task 2).
- Revision with a stored access mode that is not user selectable (e.g. free to read): unchanged revision must keep it and not offer other modes (Task 1, Task 2).
- Revision with changed affiliation where the author picks a mode: step 8 must show that mode's presets, not the article's current ones (Task 3).
- Article with no licence/rights stored: step 8 must render empty values, not fail (Task 3).
- Normal open-access article (default correction mode) must get the preset licence/rights, not be treated as a correction (Task 2).

---

### Task 1: Policy in `access_mode.get_access_mode_configuration`

**Files:**
- Modify: `wjs/plugins/wjs_submission/access_mode.py` (`get_access_mode_configuration` ~L78, remove `get_correction_access_mode_configuration` ~L324)
- Modify: `tests/test_correction.py` (`test_correction_configuration_uses_correction_data` ~L418: call `get_access_mode_configuration(user, correction)` instead of the removed function)
- Create: `tests/test_access_mode_policy.py`

**Interfaces:**
- Produces: `get_access_mode_configuration(user: Account, article: Article) -> AccessModeConfiguration | None` with the order: (1) `is_correction(article)` → `get_article_access_mode_configuration(article)`; (2) `is_revision_access_settings_unchanged(article)` → same; (3) control function result.
- Consumes (unchanged): `get_article_access_mode_configuration(article) -> AccessModeConfiguration`, `is_revision_access_settings_unchanged(article) -> bool`, `workflow.is_correction(article) -> bool`.
- Removes: `get_correction_access_mode_configuration` (callers: `step7/views.py`, `tests/test_correction.py` only).

- [ ] **Step 1: Write the failing tests** in `tests/test_access_mode_policy.py`, parametrised over flow with the control function patched (`patch("plugins.wjs_submission.access_mode.import_string", return_value=lambda user, article: calculated)`):
  - `test_policy_plain_submission_uses_control_function`: article not correction, no revision storage → returns `calculated`.
  - `test_policy_correction_returns_article_values`: patch `plugins.wjs_submission.access_mode.is_correction` to return True; article has access mode A, a custom licence, rights "original rights" → config equals `AccessModeConfiguration(A, licence, "original rights", False)`; control function not called.
  - `test_policy_revision_unchanged_returns_article_values` parametrised over `RevisionStorage.RevisionFlowType.values`: storage `data={"correspondence_author": article.correspondence_author.pk, "affiliation_pk": <submission_data.affiliation_id>}` → article values, not selectable (Review Focus: also run once with an access mode that has `user_selectable=False`).
  - `test_policy_revision_changed_uses_control_function`: `affiliation_pk` differs (or `correspondence_author` differs) → `calculated`.
  - `test_policy_revision_without_stored_access_mode_uses_control_function`: `submission_data.access_mode=None` → `calculated`.
  - `test_policy_correction_mode_per_journal`: patch `plugins.wjs_submission.access_mode.CORRECTION_ACCESS_MODE_CODE` with `{None: "open-access", "JCAP": "free-to-read", "JSTAT": "free-to-read", "JINST": "free-to-read"}` and assert `get_correction_access_mode(journal)` returns the matching `AccessMode` for the test journal code (create the `free-to-read` access mode in the test).
- [ ] **Step 2: Run** `pytest ../../wjs-submission-project/tests/test_access_mode_policy.py -v` from `janeway/src`; expected: the correction test FAILS (policy has no correction branch), others may pass.
- [ ] **Step 3: Implement** the correction branch in `get_access_mode_configuration` (import `is_correction` next to `is_revision` from `.workflow`), delete `get_correction_access_mode_configuration`, update the docstring to list the three rules.
- [ ] **Step 4: Update** `tests/test_correction.py` as described; run `pytest ../../wjs-submission-project/tests/test_access_mode_policy.py ../../wjs-submission-project/tests/test_correction.py -v`; expected: PASS (step 7 view still imports the removed function until Task 2, so do not run the view tests yet).
- [ ] **Step 5: Commit** `refactor(access_mode): apply correction and revision rules in the access mode policy`.

### Task 2: Step 7 form, view and template without licence/rights

**Files:**
- Modify: `wjs/plugins/wjs_submission/step7/forms.py`, `wjs/plugins/wjs_submission/step7/views.py`, `wjs/plugins/wjs_submission/templates/wjs_submission/step7/article_form.html`
- Modify: `tests/test_forms.py`

**Interfaces:**
- Consumes: `get_access_mode_configuration(user, article)` from Task 1.
- Produces: `SubmissionStep7Form(*, step, journal, configuration, instance, ...)` with fields `access_mode`, `special_request` only; `RevisionStep7Form` and `CorrectionStep7Form` keep their signatures.

- [ ] **Step 1: Write the failing/changed form tests** in `tests/test_forms.py` (replace the tests listed in step 3):
  - `test_step7_form_has_no_license_and_rights_fields`: `"license" not in form.fields` and `"rights" not in form.fields`.
  - `test_step7_form_without_configuration_keeps_license_and_rights`: `configuration=None`, `data={}` on an article with custom licence/rights → unchanged after `save()` (Review Focus 1).
  - `test_step7_form_fixed_configuration_forces_access_mode`: fixed config OA, submitted other mode → stored mode is OA and article licence/rights equal the OA preset after `save()` (sync), for an article that is not a correction (Review Focus 5).
  - `test_step7_form_author_choice_sets_license_and_rights` (keep as is).
  - `test_step7_form_selectable_lists_user_selectable_modes` and `test_step7_form_unchanged_revision_offers_only_stored_mode`: for the latter, build `RevisionStep7Form` with the fixed configuration returned by the policy for an unchanged revision whose stored mode is not user selectable → access mode queryset contains only that mode (Review Focus 2).
  - Keep `test_revision_access_mode_recalculated_only_if_author_or_affiliation_change` (move the policy assertions to Task 1 tests if redundant).
- [ ] **Step 2: Run** the new tests; expected FAIL (fields still exist).
- [ ] **Step 3: Implement.**
  - `step7/forms.py`: `git checkout origin/wjs-develop -- wjs/plugins/wjs_submission/step7/forms.py`, then remove the `rights`/`license` declared fields, set `Meta.fields = []`, drop every `license`/`rights` reference in `_inject_configuration_values` (loop keeps only `access_mode`), `_setup_fields` (HiddenInput lines, `Licence` queryset) and the `CorrectionStep7Form` disable list (only `access_mode`). Remove the `Licence` import if unused.
  - `step7/views.py`: `get_object` sets `self.access_mode_configuration = get_access_mode_configuration(self.request.user, obj)` for every flow; remove the `is_correction` branch and the import of `get_correction_access_mode_configuration` (keep `is_correction` for `get_form_class`).
  - Template `step7/article_form.html`: in the selectable branch remove `{% bootstrap_field form.license ... %}` and the whole `form.rights` section `div`.
  - Delete obsolete tests in `tests/test_forms.py`: `test_step7_form_save_preserves_original_rights_and_license`, `..._roundtrip_...`, `..._without_configuration` (replaced above), `test_step7_form_correction_access_mode_is_forced_and_license_rights_preserved`, `test_step7_form_open_access_article_is_not_a_correction` (replaced by the fixed-configuration test), the `step7_custom_article` fixture if no test uses it; in `test_access_mode_form` and `test_access_mode_form_data` drop assertions on `license`/`rights` fields/initial and assert licence/rights on the article after `save()` instead.
- [ ] **Step 4: Run** `pytest ../../wjs-submission-project/tests/test_forms.py ../../wjs-submission-project/tests/test_views.py ../../wjs-submission-project/tests/test_correction.py -v`; expected PASS.
- [ ] **Step 5: Commit** `refactor(step7): form handles only access mode and special request, view uses the access mode policy`.

### Task 3: Step 8 effective settings helper

**Files:**
- Modify: `wjs/plugins/wjs_submission/access_mode.py` (add helper), `wjs/plugins/wjs_submission/step8/views.py` (remove `_get_license_and_rights`, use the helper where `article_license`/`article_rights` are set), `tests/test_views.py`

**Interfaces:**
- Produces: `get_effective_access_settings(article: Article) -> tuple[AccessMode | None, Licence | None, str]` in `access_mode.py`. Access mode: `article.revisionstorage.data["access_mode"]` (as `AccessMode`) when `is_revision(article)`, else `article.submission_data.access_mode`. Licence/rights: the article's values, except for a revision whose stored mode id differs from `submission_data.access_mode_id`: the `AccessModeJournal` presets (`licence`, `copyright`) of the stored mode for the article journal (flags ignored). Rights are returned as `""` when empty.
- Context keys kept: `article_license`, `article_rights` (template unchanged).

- [ ] **Step 1: Write failing tests** in `tests/test_views.py` / a new `tests/test_effective_access_settings.py`: plain article returns its stored values; revision with the same mode returns the article's values; revision with a different stored mode returns that mode's presets even when override flags are True; article without licence/rights returns `(mode, None, "")` (Review Focus 3, 4). Keep `test_submission_step8_shows_article_license_and_rights` passing.
- [ ] **Step 2: Run** them; expected FAIL (`get_effective_access_settings` missing).
- [ ] **Step 3: Implement** the helper and replace `_get_license_and_rights` usage in `step8/views.py` (the context `access_mode` entry keeps using `AccessModeJournal` as today).
- [ ] **Step 4: Run** `pytest ../../wjs-submission-project/tests/test_views.py ../../wjs-submission-project/tests/test_effective_access_settings.py -v`; expected PASS.
- [ ] **Step 5: Commit** `refactor(step8): show effective access settings through a single helper`.

### Task 4: Documentation, full run, hand-over

**Files:**
- Wiki: `wjs/specs` page `Submission2025/ErratumAddendum` (via the GitLab MCP; keep `title` param equal to the slug to avoid moving the page)

- [ ] **Step 1: Update the wiki:** replace the "Behavior" and "Relation with revisions" subsections with the rules table from the spec; keep the per-journal tables; add a revision row.
- [ ] **Step 2: Run the full suite** `pytest ../../wjs-submission-project/tests -n8 -q` from `janeway/src`; expected: all pass.
- [ ] **Step 3: Remind the user** that `correction/logic.py` should later be rewritten with the `revision/logic.py` pattern (memory `correction-logic-rewrite-todo`).
- [ ] **Step 4: Push** only on explicit user request (branch already has a remote; no history rewrite is needed).
