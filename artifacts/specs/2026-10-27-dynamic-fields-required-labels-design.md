# Submission form fields: table-driven dynamic fields, no placeholders, explicit "Required" markers

Date: 2026-10-27. Language: English.

## Problem

- `SubmissionStep1Form` builds the journal's additional fields (Janeway `submission.models.Field`) with an
  if/elif chain that knows only `text`, `textarea` and `check`. Janeway also offers `select`, `email` and `date`;
  an element of those kinds breaks the form. The text kind shows its help text as a placeholder, while the other
  kinds show it as help text.
- The submission templates let `django_bootstrap5` turn labels into placeholders, so fields show a placeholder
  that repeats or replaces the label.
- Sections whose label is flagged required do not say so in text: only the first-step fields carry the bold
  "Required" help text, so the flag is a styling class alone.
- In the funding modal the funding statement is a default-sized textarea.

## Goals

- Every Janeway field kind (`text`, `textarea`, `check`, `date`, `select`, `email`) builds a working step 1 form
  field, through one table rather than a chain of branches.
- Step 1 never receives an additional field of a kind it cannot build.
- Submission templates render fields without placeholders; help text is shown as help text, for all kinds.
- Sections that are required show an explicit bold "Required" marker, and the marker appears only when the
  section really is required.
- The funding statement is a four-row textarea in both the submission and the revision funding forms.

## Non-goals

- No change to the hierarchical or flat keyword validation (specs#3280).
- No new JavaScript and no change to step workflow, models or migrations.
- No change to the `data-modal-size` mechanism: the funding modal keeps `data-modal-size="lg"`, which
  `#htmxModal .modal-dialog:has(...)` in the theme's `_wjs_base.scss` uses to widen the modal.

## Design

**Field table (`helpers/forms.py`).**
- `FieldSpec` (frozen dataclass): `field_class`, optional `widget_class`, optional `widget_attrs` (default
  `{"div_class": element.width}`), `extra_kwargs(element)`, `help_text_as_placeholder` (default `False`), and a
  `build(element)` method that instantiates the form field with the required flag, help text and widget.
- `FIELD_SPECS`: kind → `FieldSpec`, covering exactly Janeway's `field_kind_choices()`.
- `map_dynamic_field(element, instance) -> forms.Field | None`: builds the field from `FIELD_SPECS`, labels it
  with the element name, prefixes the help text with `required_help_text` when the element is required, and uses
  an existing `FieldAnswer` as the initial value for a saved article. A kind with no spec returns `None`.

**Step 1 (`step1/forms.py`).** `_additional_fields` is filtered with `kind__in=FIELD_SPECS`, so every loop in the
form (rendering, validation, saving, revision storage) sees only buildable elements and no `None` field can be
stored. `__init__` assigns `map_dynamic_field(element, self.instance)` for each element.

**Templates.**
- Steps 1, 4, 5, 6 and 7 pass `placeholder=""` to every `bootstrap_field`, including the file-upload and funding
  modals.
- A bold "Required" block is added where the section label is required:
  - conditional on the field: step 1 `competing_interests` and `comments_editor` (`form.<field>.field.required`),
    step 6 DAS and CAS (inside the existing `not form.das.is_hidden` / `not form.cas.is_hidden` blocks), step 3
    keywords (only when the journal's minimum keyword count `keywords_count.0` is above zero). The keywords
    weight marker is a separate element outside the weights container, because `keywords.js` empties that
    container on every update; it starts hidden (`d-none`) and `keywords.js` shows and hides it together with the
    weights info block, so it is visible only while weights are shown;
  - unconditional, because hidden required inputs always enforce them: step 4 selected authors and corresponding
    author, step 6 manuscript file.
- Theme (`wjs-themes`, `_submission-keywords.scss`): the last keyword group's bottom margin goes from `mb-5` to
  `mb-2`, so the keywords "Required" marker sits next to the table; the marker keeps its own `mb-5` after it.
  Needs `manage.py build_assets` to take effect.
- Markup tidy-ups: step 1 "Validate ArXiv ID" button indentation, non-breaking spaces in the step 4 placeholder
  sample text, one blank line after `{% load %}` in `step4/article_form.html`.

**Funding (`step7/forms.py`).** `AddFundingForm.Meta` and `RevisionAddFundingForm.Meta` both set
`widgets = {"funding_statement": forms.Textarea(attrs={"rows": 4})}`. The revision form declares its own `Meta`,
so it does not inherit the widget and needs the entry itself.

## Tests (red first)

- `tests/test_dynamic_fields.py`: each kind builds the expected field and widget; `FIELD_SPECS` matches Janeway's
  kinds; select choices; label and "Required" help text; text help text is not a placeholder; unsupported kind
  returns `None`; saved answer becomes initial; the step 1 form ignores an element of unsupported kind.
- `tests/test_required_markers.py`: four-row funding textarea for both forms; step 3 marker follows the minimum
  keyword count on the flat and hierarchical templates; the step 3 weights marker is rendered hidden, only for
  hierarchical journals with a minimum (its show/hide in `keywords.js` was checked by hand in the browser: there
  is no JS test runner); step 6 markers follow `enable_das`/`enable_cas`; the
  funding modal keeps `data-modal-size="lg"`.

## Constraints

- Ruff (pinned `v0.11.13`), `ruff format`, djlint (`--profile=django`) and `pre-commit run --all-files` clean.
  Do not rewrite `# noqa` to `# ruff:ignore`: the pinned ruff does not know it.
- Templates keep the repo's 2-space indentation, with tags indented as the surrounding markup.
