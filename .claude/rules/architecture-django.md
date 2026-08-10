---
description: Architecture rules for Django — SOLID principles, design patterns, and app conventions
---

# WJS Django Architecture Rules

## SOLID principles

- **Single Responsibility**: one class/module = one concern
- **Open/Closed**: extend via subclassing or registry, not by editing core code
- **Liskov Substitution**: subclasses must honour parent contracts
- **Interface Segregation**: small focused interfaces over fat ones
- **Dependency Inversion**: depend on abstractions; inject concrete implementations

## Model architecture

All model filtering (except filtering logic which uses django-filter for user input based filters) must be wrapped
in custom queryset attached to each model. Avoid filtering directly against `.objects` in views, forms, or business
logic classes — always go through a queryset method defined on the model's manager, so the filtering logic stays
in one place and is reusable and testable in isolation.

## Forms architecture

Forms are the default place for save-time logic in this codebase — not just thin
validate-and-save wrappers. A form's `save()`/`clean()` is expected to:

- validate input
- save the model and its related objects
- create or update related objects directly (e.g. `AddAuthorForm.save()` creating a
  `FrozenAuthor`, `AddCollaborationForm.save()` creating an `ArticleCollaboration`)
- handle file uploads (`core.files.save_file_to_article`, as in the step1 cover-letter handling
  and step6's `UploadArticleForm`/`RevisionUploadArticleForm`)
- write into `RevisionStorage.data` when the form belongs to a revision step (e.g.
  `RevisionStep4Form.save()`, `RevisionStep5Form.save()`)

This kind of logic stays inline in the form. Do not extract it into a separate business-logic
class just because a `save()` method has grown past a couple of lines — most side effects in this
codebase are, and should stay, form-local.

**Only promote logic into a dedicated business-logic class (see below) when it is clearly
encapsulated** — reused from more than one form/view, or self-contained enough to deserve its own
name and tests independent of any single form. Examples already in this codebase:

- `arxiv.py::HandleArticleCreation` — merges arXiv-imported metadata with form data when
  creating/updating an `Article`; called from `SubmissionStep1Form.save()`.
- `step3/logic.py::HandleKeywordSelection` — parses, validates and persists keyword weights;
  called from `SubmissionStep3Form.save()`.
- `step4/logic.py::TableMoveDeleteHandler` — generic reorder/delete for ordered per-article
  tables (authors, collaborations); shared across multiple views rather than owned by one form.
- `step8/logic.py::CompleteSubmission` — orchestrates the several Janeway events/signals fired on
  final submission (first submission vs. revision); called from `SubmissionStep8Form.save()`.
- `revision/logic.py`'s `BaseSetupRevisionStorage` subclasses — build a `RevisionStorage`
  snapshot; shared by the three revision-start views (`RevisionStartConfirmView` / `-Metadata` /
  `-Full`), which is why this one lives at the view level rather than in a form.

When a form *does* delegate to a business logic class, its `save()` must instantiate it, call the
`run` method, refresh the instance and return it. If any ValidationError is raised, it must be
added as a non-field-related error.

Sample pattern (for the cases above that warrant it):

```python
def save(self, commit: bool = True) -> Booking:
    try:
        service = self.get_logic_instance()
        service.run()
    except ValidationError as e:
        self.add_error(None, e)
        raise
    self.instance.refresh_from_db()
    return self.instance
```

The form must be independent from the view and the request data: all context-related data must be passed to the form as arguments to the constructor.

## Business logic architecture

Reach for a business logic class only for logic that's clearly encapsulated in the sense
described in *Forms architecture* above — reused across more than one form/view, or complex
enough (multi-step orchestration, multiple signals/events, generic/parametrized operations) to
deserve its own name and tests outside any single form's `save()`. It is not the default home for
form side effects; when in doubt, keep the logic in the form.

When a business logic class is needed, it must be designed as a dataclass that defines as attribute all the data required to run the logic (except runtime-behavior altering arguments).

It must define a `run` method that executes the logic, which can take optional parameters to the behavior.

The business logic class must be independent from the request data: all context-related data must be passed as arguments to the constructor.

Avoid to overload a business logic class with too much logic: it should only handle a single use case. If multiple use cases share a lot of logic, consider extracting the shared behaviour into a mixin or a separate helper class that each business logic class composes, rather than subclassing one business logic class from another.

The `run` method must run its logic in a transaction. If race conditions are possible, consider using `select_for_update` method to fetch a locked instance.

After the transaction is initiated and object is fetched (if locking is needed), the logic must check that requirements are met before proceeding: if any requirement fails,
a ValidationError must be raised in the `run` method.

The business logic class must be executable outside of a view / form.

## Views architecture

View must include the least amount of code possible.

The goal of a view must be gather user input and create the context for template rendering.

Objects filtering must be offloaded to django-filter when more that 3 user filter criteria is used or when filters requires
user to select items from an existing list. Implicit filters (like permission-based filters, tenant scoping, or
soft-delete visibility) belong in the model's custom queryset (see *Model architecture* above), not duplicated in
every view.

Form-based views must offload all the logic to the linked form for validation, save logic. Not
every view needs a Django `Form`, though: a self-contained action endpoint (typically an HTMX
button/row action, e.g. `ReorderAuthorsView`/`SaveCorrespondingAuthorView`/
`ReorderCollaborationsView` in `step4/views.py`, `DeleteFundingView` in `step7/views.py`) may
instead be a plain `DetailView`/`TemplateView` whose `post()` reads the request directly and calls
a business-logic class (e.g. `TableMoveDeleteHandler`) itself — there is no form to offload to
because there's no user-editable form data, just an action to perform.

When the same logic is used in multiple views, create a mixin to wrap the logic and subclass views classes from this mixin
to reuse the logic.

**In this codebase, `form_valid`/`form_invalid` overrides are mostly used for response shaping,
not for catching `ValidationError`** — e.g. re-rendering an HTMX partial and setting
`HX-Trigger`/`HX-Retarget` headers on success or failure (`step4`'s `ModalRenderingMixin`,
`step6`'s `UploadSubmissionFile`), passing extra kwargs through to `form.save()`
(`step5`'s `SubmissionStep5View.form_valid` calls `form.save(request=self.request)`), or adding a
user-facing success message (`step8`'s `SubmissionStep8View.form_valid`). Where a view has no
such response-shaping need, it has no `form_valid` override at all and relies on Django's default
(`step1`, `step2`, `step3`).

**Known gap — the `ValidationError` → `form_invalid` wrapper below is not currently applied
anywhere in this codebase**, even where it's arguably needed: `SubmissionStep1Form.save()` and
`SubmissionStep3Form.save()` both catch a business-logic class's `ValidationError`, call
`self.add_error(None, e)`, and re-raise — but `SubmissionStep1View`/`SubmissionStep3View` have no
`form_valid` override to catch that re-raised exception, so today it propagates as an unhandled
error instead of re-rendering the form with the message attached. When you *do* have a view
backed by a form whose `save()` can raise `ValidationError`, wire up the wrapper below — don't
assume it's already handled just because the form calls `add_error`.

Sample code:

```python
def form_valid(self, form: BookingForm) -> HttpResponse:
    try:
        return super().form_valid(form)
    except (ValidationError) as e:
        return super().form_invalid(form)
```

## Registry / Decorator pattern

Prefer registries over direct imports for extensible, plugin-like behaviour. Components
register themselves; core code iterates the registry rather than importing each component.

## Dependency Injection

Pass dependencies into constructors or factory functions. Avoid module-level singletons
and global state that makes testing and substitution difficult.

## Reusable packages vs project code

- Reusable logic → extract to a `nephila-apps` / `nephila-widgets` package with its own
  towncrier changelog and semver versioning
- Project-specific logic → keep in the project app; do not prematurely extract
- The boundary: if two unrelated projects need the same code, it belongs in a package

## Dependency selection

- Always verify the compatibility of the selected library with the project
- Avoid using libraries that are not actively maintained
- Prefer libraries with a permissive license (MIT, Apache, BSD, etc.)
