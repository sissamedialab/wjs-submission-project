# Dynamic fields table and "Required" markers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build every Janeway field kind in step 1 from one table, drop auto placeholders in the submission templates, show explicit "Required" markers only where a section is required, and size the funding statement textarea.

**Architecture:** A `FIELD_SPECS` table in `helpers/forms.py` replaces the if/elif chain in `SubmissionStep1Form`; the form only loads elements whose kind is in the table. Templates gain `placeholder=""` and conditional "Required" blocks. Funding forms set a four-row textarea widget.

**Tech Stack:** Django, django-bootstrap5, pytest (run from `janeway/src`, see `.claude/rules/tests.md`).

**Spec:** `artifacts/specs/2026-10-27-dynamic-fields-required-labels-design.md`

## Global Constraints

- Double quotes, line length 119, imperative docstrings; ruff (pinned `v0.11.13`) + `ruff format` clean.
- Do not rewrite `# noqa` to `# ruff:ignore` (the pinned ruff does not know it).
- Templates: 2-space indentation, tags indented like the surrounding markup; `djlint --profile=django` clean.
- Tests: bare `assert` needs a message; tests that touch the DB carry `@pytest.mark.django_db`.
- No migrations, no JS, no change to keyword validation (specs#3280).

## Review Focus

- Journal field element of an unsupported kind: step 1 builds without it and nothing stores a `None` field.
- Journal with a minimum of 0 keywords: no step 3 "Required" marker, on the flat and the hierarchical template.
- DAS/CAS disabled: no step 6 marker for it; the manuscript marker always shows.
- Revision funding form: same four-row textarea as the submission one (it has its own `Meta`).
- Funding modal keeps `data-modal-size="lg"` (the theme stylesheet widens the modal from it).
- Step 3 weights marker shows only while weights are shown, and survives the JS emptying the weights container.

---

### Task 1: Field table and step 1 form

**Files:**
- Modify: `wjs/plugins/wjs_submission/helpers/forms.py`
- Modify: `wjs/plugins/wjs_submission/step1/forms.py`
- Test: `tests/test_dynamic_fields.py`

**Interfaces:**
- Produces: `FieldSpec` (frozen dataclass: `field_class`, `widget_class=None`, `widget_attrs=None`, `extra_kwargs`, `help_text_as_placeholder=False`; `build(element: Field) -> forms.Field`), `FIELD_SPECS: dict[str, FieldSpec]` keyed by Janeway field kind, and `map_dynamic_field(element: Field, instance: Article | None) -> forms.Field | None`.

- [ ] **Step 1: Write the failing tests in `tests/test_dynamic_fields.py`**
  - `test_map_dynamic_field_builds_the_field_for_each_kind`, parametrized: text → `CharField`/`TextInput`; textarea → `WjsMiniHTMLFormField`; check → `BooleanField`/`CheckboxInput`; date → `CharField`/`HTMLDateInput`; select → `ChoiceField`/`Select`; email → `EmailField`/`TextInput`.
  - `test_field_specs_cover_every_janeway_field_kind`: `set(FIELD_SPECS) == {kind for kind, _ in field_kind_choices()}`.
  - `test_map_dynamic_field_select_renders_the_element_choices`: choices `"first|second"` → labels `["first", "second"]`.
  - `test_map_dynamic_field_label_and_required_help_text`, parametrized text/textarea/email: label is the element name; required help text contains "Required" and the element help text; optional does not contain "Required".
  - `test_map_dynamic_field_text_shows_help_text_not_placeholder`: `help_text == "Some help"`, no `placeholder` in widget attrs.
  - `test_map_dynamic_field_unsupported_kind_returns_none`.
  - `test_map_dynamic_field_uses_the_saved_answer_as_initial`: saved article → answer; unsaved `Article()` → `None`.
  - `test_step1_form_ignores_elements_of_unsupported_kind`: a `supported` text element is in `form.fields`, an `unsupported`-kind element is not, and no value in `form.fields` is `None`.
  - Failure messages on every assert.

- [ ] **Step 2: Run to verify they fail**

  Run (from `janeway/src`): `pytest ../../wjs-submission-project/tests/test_dynamic_fields.py -v`
  Expected: import errors for `FIELD_SPECS`/`map_dynamic_field` (then, once Step 3 exists without the filter, the last test FAILS).

- [ ] **Step 3: Implement `FieldSpec`, `FIELD_SPECS` and `map_dynamic_field` in `helpers/forms.py`**

  Per the spec's Design. `build` passes `required`, `help_text` (empty when `help_text_as_placeholder`), `extra_kwargs(element)`, and the widget with `widget_attrs` (default `{"div_class": element.width}`, plus `placeholder` when `help_text_as_placeholder`). Table entries: `text` (`CharField`, `TextInput`), `textarea` (`WjsMiniHTMLFormField`), `check` (`BooleanField`, `CheckboxInput`, `widget_attrs={"is_checkbox": True}`), `date` (`CharField`, `HTMLDateInput`), `select` (`ChoiceField`, `Select`, choices from `review.logic.render_choices(element.choices)`), `email` (`EmailField`, `TextInput`). Use `lambda _element: {}` as the `extra_kwargs` default. `map_dynamic_field` labels the field with the element name and wraps the help text with `required_help_text` for required elements.

- [ ] **Step 4: Use it in `step1/forms.py`**

  Filter `_additional_fields` with `kind__in=FIELD_SPECS`; in `__init__` assign `self.fields[element.name] = map_dynamic_field(element, self.instance)` and delete the old branches and the now unused imports.

- [ ] **Step 5: Run to verify they pass**

  Run: `pytest ../../wjs-submission-project/tests/test_dynamic_fields.py ../../wjs-submission-project/tests/test_forms.py ../../wjs-submission-project/tests/test_logic.py -q`
  Expected: PASS.

### Task 2: Templates — no placeholders, "Required" markers

**Files:**
- Modify: `wjs/plugins/wjs_submission/templates/wjs_submission/step{1,3,4,5,6,7}/…` (the files listed by `git diff --name-only` for this change, including `step6/includes/upload_file.html` and `step7/add_funding_modal.html`)
- Test: `tests/test_required_markers.py`

**Interfaces:**
- Consumes: `keywords_count` (min, max) from `SubmissionStep3View.get_context_data`; `form.das`/`form.cas` hidden state from `SubmissionStep6Form`.

- [ ] **Step 1: Write the failing tests in `tests/test_required_markers.py`**
  - A module constant `REQUIRED_MARKER = re.compile(r'<div class="mb-\d"><strong>Required</strong></div>')` (the URL fields' help text also renders `<strong>Required</strong>`, so match the marker div only).
  - `test_step3_required_marker_follows_the_minimum_keywords`, parametrized on hierarchical/flat × minimum 1/0 (patch `KEYWORDS_INTERVAL_PER_JOURNAL` with `monkeypatch.setitem` for the `None` key and the journal code): marker present only when the minimum is 1.
  - `test_step6_required_markers_follow_the_enabled_statements`, parametrized on `enable_das` × `enable_cas` (`save_setting`, `article.current_step = 6`): marker count is `1 + enable_das + enable_cas`.
  - `test_step3_weights_required_marker_is_rendered_hidden`, parametrized (hierarchical, min 1) / (hierarchical, min 0) / (flat, min 1): a `keywords-weight-required` marker exists with class `d-none` only in the first case.

- [ ] **Step 2: Run to verify they fail**

  Run: `pytest ../../wjs-submission-project/tests/test_required_markers.py -v -k "step3 or step6"`
  Expected: the minimum-0 step 3 cases FAIL (the step 6 cases already match the existing conditional blocks and pin that behaviour).

- [ ] **Step 3: Edit the templates**
  - Add `placeholder=""` to every `bootstrap_field` in steps 1, 4, 5, 6, 7 (including `upload_file.html` and `add_funding_modal.html`; add the missing space in `placeholder="" %}` there).
  - Add `<div class="mb-N"><strong>Required</strong></div>` blocks: conditional on `form.competing_interests.field.required` and `form.comments_editor.field.required` in step 1; on `keywords_count.0` for the three step 3 spots; inside the existing `not form.das.is_hidden`/`not form.cas.is_hidden` blocks in step 6; unconditional for step 4 selected authors, step 4 corresponding author and the step 6 manuscript file.
  - Tidy-ups: indent the markers like their siblings; re-indent the step 1 "Validate ArXiv ID" button; replace the non-breaking spaces in the step 4 placeholder sample text; one blank line after `{% load %}` in `step4/article_form.html`.

- [ ] **Step 3b: Weights marker and spacing**
  - Put the step 3 weights marker outside `.wjs-submission-form__keywords-weight-container` (the JS empties it), as `<div class="wjs-submission-form__keywords-weight-required d-none mb-2">` under `{% if keywords_count.0 %}`.
  - In `static/js/keywords.js` `addKeywordWeightList`, add `d-none` to it when no keyword is selected and remove it otherwise, next to the existing `weightInfo` handling.
  - In `wjs-themes` `_submission-keywords.scss`, change the last `.accordion-item`'s `@extend .mb-5` to `.mb-2`; run `manage.py build_assets`.
  - Check by hand: marker visible on load with saved keywords, hidden after deselecting all, visible after selecting one.

- [ ] **Step 4: Run to verify they pass, then lint**

  Run: `pytest ../../wjs-submission-project/tests/test_required_markers.py -q`, then `djlint --profile=django --lint <changed templates>` and `git diff HEAD --check`.
  Expected: PASS; djlint 0 errors; no whitespace errors.

### Task 3: Funding statement textarea and modal size

**Files:**
- Modify: `wjs/plugins/wjs_submission/step7/forms.py` (`AddFundingForm.Meta`, `RevisionAddFundingForm.Meta`)
- Modify: `wjs/plugins/wjs_submission/templates/wjs_submission/step7/add_funding_modal.html` (`data-modal-size="lg"` on `.modal-header`)
- Test: `tests/test_required_markers.py`

- [ ] **Step 1: Write the failing tests**
  - `test_funding_statement_uses_a_four_rows_textarea`, parametrized on `AddFundingForm` and `RevisionAddFundingForm`: `form_class.base_fields["funding_statement"].widget.attrs.get("rows") == 4`.
  - `test_add_funding_modal_asks_for_the_large_size`: GET `reverse("add-funding", kwargs={"article_id": article.pk})` as the owner → 200 and `data-modal-size="lg"` in the content.

- [ ] **Step 2: Run to verify they fail**

  Run: `pytest ../../wjs-submission-project/tests/test_required_markers.py -v -k "funding or modal"`
  Expected: the revision form case and the modal case FAIL until implemented.

- [ ] **Step 3: Implement**

  Add `widgets = {"funding_statement": forms.Textarea(attrs={"rows": 4})}` to both `Meta` classes (the revision `Meta` does not inherit it) and `data-modal-size="lg"` to the modal header.

- [ ] **Step 4: Run to verify they pass**

  Run: `pytest ../../wjs-submission-project/tests/test_required_markers.py -q`
  Expected: PASS.

### Task 4: Whole-change verification

- [ ] **Step 1:** Run the full suite from `janeway/src`: `pytest --create-db -n7 ../../wjs-submission-project`. Expected: all pass.
- [ ] **Step 2:** `pre-commit run --all-files`, `djlint --profile=django --lint <changed templates>`, `git diff HEAD --check`. Expected: clean (the three ruff `noqa-comments` findings from a newer local ruff are not to be "fixed").
