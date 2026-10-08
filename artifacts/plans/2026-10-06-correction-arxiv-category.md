# Errata / Addenda arXiv category Implementation Plan

> **Update 2026-10-07 (MR !166 review):** the backfill (section 2 / Task 2) was dropped —
> there are no live errata/addenda in production, so there is nothing to backfill. Only the
> copy at creation time ships.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Errata/addenda show the arXiv category next to the arXiv id on the article page
(`wjs_article_details`), for new and existing corrections.

**Architecture:** `SetupCorrectionStorage._populate_metadata()` copies `arxiv_category` from the
corrected article's `ArticleSubmission` into the correction's. A data migration backfills
existing corrections found through Hydra `LinkedArticle` rows (`erratum`/`addendum`); its body
lives in `data.py` so it can be tested directly.

**Tech Stack:** Django 5.2, pytest + pytest-django, Janeway plugins (`plugins.hydra`,
`plugins.wjs_submission`).

**Spec:** `artifacts/specs/2026-10-06-correction-arxiv-category-design.md`

## Global Constraints

- Single repository: wjs-submission-project. No template change.
- Never overwrite a non-empty `arxiv_category` on a correction.
- Never create an `ArticleSubmission` in the migration.
- Migration reverse is `migrations.RunPython.noop`.
- Migration depends on `("wjs_submission", "0023_remove_articlesubmission_special_request_updated_and_more")`
  and `("hydra", "0001_initial")` (hydra is a mandatory plugin; `0001_initial` already provides
  `from_article`, `to_article` and `relationship`, the only fields the backfill reads).
- Documentation, comments, commit messages: English.
- Tests run from `janeway/src`: `pytest ../../wjs-submission-project/tests/test_correction.py`
  (see `.claude/rules/tests.md`). Migrations are skipped in tests, so the backfill is tested by
  calling the function with `django.apps.apps`.

## Review Focus

1. Corrected article without `ArticleSubmission` (test fixtures and legacy/imported papers have
   none) → correction setup succeeds, category stays empty. (Task 1, Step 1)
2. Corrected article with `ArticleSubmission` but empty category → correction stays empty, no
   error. (Task 2, Step 1)
3. Backfill re-run → no further changes (idempotent). (Task 2, Step 1)
4. Article with several corrections (erratum + addendum) → each gets the category. (Task 2, Step 1)
5. Non-correction Hydra links (e.g. `commentary`) → untouched by the backfill. (Task 2, Step 1)

---

### Task 1: Copy arXiv category when a correction is created

**Files:**
- Modify: `wjs/plugins/wjs_submission/correction/logic.py` (`_populate_metadata`, the
  `ArticleSubmission.objects.get_or_create(...)` line and its docstring)
- Test: `tests/test_correction.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: corrections created by `SetupCorrectionStorage.run()` have
  `submission_data.arxiv_category` equal to the corrected article's (or `""`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_correction.py` (add `ArticleSubmission` import from
`plugins.wjs_submission.models` after the hydra `importorskip`, with `# noqa: E402`):

```python
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("relationship", "section_fixture"),
    [(ERRATUM, "erratum_section"), (ADDENDUM, "addendum_section")],
)
def test_run_copies_arxiv_category(
    published_article_with_frozen_authors: Article,
    request_user: Account,
    install_plugins: Callable,
    relationship: str,
    section_fixture: str,
    request: pytest.FixtureRequest,
):
    """The correction inherits the arXiv category of the corrected article."""
    request.getfixturevalue(section_fixture)
    ArticleSubmission.objects.create(article=published_article_with_frozen_authors, arxiv_category="astro-ph.CO")
    setup = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=relationship,
        request=MagicMock(user=request_user),
    )
    to_article = setup.run()
    to_article.refresh_from_db()
    assert to_article.submission_data.arxiv_category == "astro-ph.CO"


@pytest.mark.django_db
def test_run_without_from_article_submission_data(
    published_article_with_frozen_authors: Article,
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """A corrected article without ArticleSubmission leaves the correction's category empty."""
    assert not ArticleSubmission.objects.filter(article=published_article_with_frozen_authors).exists()
    setup = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    )
    to_article = setup.run()
    to_article.refresh_from_db()
    assert to_article.submission_data.arxiv_category == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `janeway/src`):
`pytest ../../wjs-submission-project/tests/test_correction.py -k "copies_arxiv_category or without_from_article_submission_data" -v`
Expected: the two `test_run_copies_arxiv_category` cases FAIL (`'' == 'astro-ph.CO'`);
`test_run_without_from_article_submission_data` PASSES (it pins current behavior).

- [ ] **Step 3: Implement**

In `_populate_metadata()`, replace:

```python
        # Create ArticleSubmission wrapper (needed by steps 6/7).
        ArticleSubmission.objects.get_or_create(article=self.to_article)
```

with:

```python
        # Create ArticleSubmission wrapper (needed by steps 6/7).
        submission_data, _ = ArticleSubmission.objects.get_or_create(article=self.to_article)
        # Corrections skip the arXiv step: inherit the category shown next to the arXiv id.
        submission_data.arxiv_category = (
            ArticleSubmission.objects.filter(article=self.from_article)
            .values_list("arxiv_category", flat=True)
            .first()
            or ""
        )
        submission_data.save()
```

Add to the method docstring bullet list:
`- arxiv_category = from_article.submission_data.arxiv_category (empty if missing)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest ../../wjs-submission-project/tests/test_correction.py -v`
Expected: all PASS (including the pre-existing tests).

- [ ] **Step 5: Commit (only if per-change commits were chosen in flow step 4)**

```bash
git add wjs/plugins/wjs_submission/correction/logic.py tests/test_correction.py
git commit -m "fix: copy arXiv category to errata and addenda (#3212)"
```

---

### Task 2: Backfill arXiv category on existing corrections

**Files:**
- Modify: `wjs/plugins/wjs_submission/data.py` (new function at the end)
- Create: `wjs/plugins/wjs_submission/migrations/0024_backfill_correction_arxiv_category.py`
- Test: `tests/test_correction.py`

**Interfaces:**
- Consumes: Hydra `LinkedArticle` (`from_article`, `to_article`, `relationship`);
  `ArticleSubmission.article` (OneToOne, `related_name="submission_data"`).
- Produces: `backfill_correction_arxiv_category(apps, schema_editor) -> None` in
  `plugins.wjs_submission.data`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_correction.py`. Imports: add `from django.apps import apps as django_apps`
near the top imports, `from plugins.wjs_submission.data import backfill_correction_arxiv_category  # noqa: E402`
next to the other plugin imports, and extend the existing `from tests.conftest import _user` to
`from tests.conftest import _article, _user  # noqa: E402`.

```python
def _correction(journal, sections, author, coauthor, published, relationship: str) -> Article:
    """Create an article linked to ``published`` with the given Hydra relationship."""
    correction = _article(author, coauthor, journal, sections)
    LinkedArticle.objects.create(from_article=published, to_article=correction, relationship=relationship)
    return correction


@pytest.mark.django_db
def test_backfill_fills_empty_category(published_article, journal, sections, author, coauthor):
    """Existing errata and addenda with an empty category get the corrected article's one."""
    ArticleSubmission.objects.create(article=published_article, arxiv_category="hep-th")
    erratum = _correction(journal, sections, author, coauthor, published_article, ERRATUM)
    addendum = _correction(journal, sections, author, coauthor, published_article, ADDENDUM)
    ArticleSubmission.objects.create(article=erratum)
    ArticleSubmission.objects.create(article=addendum)

    backfill_correction_arxiv_category(django_apps, None)

    assert ArticleSubmission.objects.get(article=erratum).arxiv_category == "hep-th"
    assert ArticleSubmission.objects.get(article=addendum).arxiv_category == "hep-th"
    # Idempotent: a second run changes nothing.
    backfill_correction_arxiv_category(django_apps, None)
    assert ArticleSubmission.objects.get(article=erratum).arxiv_category == "hep-th"


@pytest.mark.django_db
def test_backfill_keeps_existing_category(published_article, journal, sections, author, coauthor):
    """A correction with a non-empty category is never overwritten."""
    ArticleSubmission.objects.create(article=published_article, arxiv_category="hep-th")
    erratum = _correction(journal, sections, author, coauthor, published_article, ERRATUM)
    ArticleSubmission.objects.create(article=erratum, arxiv_category="gr-qc")

    backfill_correction_arxiv_category(django_apps, None)

    assert ArticleSubmission.objects.get(article=erratum).arxiv_category == "gr-qc"


@pytest.mark.django_db
def test_backfill_skips_correction_without_submission_data(
    published_article, journal, sections, author, coauthor
):
    """No ArticleSubmission is created for a correction that has none."""
    ArticleSubmission.objects.create(article=published_article, arxiv_category="hep-th")
    erratum = _correction(journal, sections, author, coauthor, published_article, ERRATUM)

    backfill_correction_arxiv_category(django_apps, None)

    assert not ArticleSubmission.objects.filter(article=erratum).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("from_has_submission_data", [True, False])
def test_backfill_skips_when_corrected_article_has_no_category(
    published_article, journal, sections, author, coauthor, from_has_submission_data: bool
):
    """Nothing changes when the corrected article has no (or an empty) category."""
    if from_has_submission_data:
        ArticleSubmission.objects.create(article=published_article, arxiv_category="")
    erratum = _correction(journal, sections, author, coauthor, published_article, ERRATUM)
    ArticleSubmission.objects.create(article=erratum)

    backfill_correction_arxiv_category(django_apps, None)

    assert ArticleSubmission.objects.get(article=erratum).arxiv_category == ""


@pytest.mark.django_db
def test_backfill_ignores_non_correction_links(published_article, journal, sections, author, coauthor):
    """Hydra links other than erratum/addendum are left alone."""
    ArticleSubmission.objects.create(article=published_article, arxiv_category="hep-th")
    commentary = _correction(journal, sections, author, coauthor, published_article, "commentary")
    ArticleSubmission.objects.create(article=commentary)

    backfill_correction_arxiv_category(django_apps, None)

    assert ArticleSubmission.objects.get(article=commentary).arxiv_category == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest ../../wjs-submission-project/tests/test_correction.py -k backfill -v`
Expected: collection ERROR — `ImportError: cannot import name 'backfill_correction_arxiv_category'`.

- [ ] **Step 3: Implement the function**

Append to `wjs/plugins/wjs_submission/data.py`:

```python
def backfill_correction_arxiv_category(apps, schema_editor):
    """
    Copy the arXiv category from corrected articles to their existing errata/addenda.

    Corrections skip the arXiv submission step, so their ``ArticleSubmission.arxiv_category``
    was left empty before ``SetupCorrectionStorage`` started copying it (#3212). Only empty
    categories are filled; corrections without ``ArticleSubmission`` are skipped.
    """
    LinkedArticle = apps.get_model("hydra", "LinkedArticle")
    ArticleSubmission = apps.get_model("wjs_submission", "ArticleSubmission")

    # Literal values of correction.logic.ERRATUM/ADDENDUM: importing that module here would
    # pull in live models, which migrations must not use.
    links = LinkedArticle.objects.filter(relationship__in=("erratum", "addendum")).values_list(
        "from_article_id", "to_article_id"
    )
    for from_article_id, to_article_id in links:
        correction_data = ArticleSubmission.objects.filter(article_id=to_article_id, arxiv_category="").first()
        if correction_data is None:
            continue
        category = (
            ArticleSubmission.objects.filter(article_id=from_article_id)
            .exclude(arxiv_category="")
            .values_list("arxiv_category", flat=True)
            .first()
        )
        if not category:
            continue
        correction_data.arxiv_category = category
        correction_data.save(update_fields=["arxiv_category"])
```

- [ ] **Step 4: Create the migration**

`wjs/plugins/wjs_submission/migrations/0024_backfill_correction_arxiv_category.py`:

```python
from django.db import migrations
from plugins.wjs_submission.data import backfill_correction_arxiv_category


class Migration(migrations.Migration):
    dependencies = [
        ("wjs_submission", "0023_remove_articlesubmission_special_request_updated_and_more"),
        # Provides LinkedArticle (from_article, to_article, relationship).
        ("hydra", "0001_initial"),
    ]

    operations = [migrations.RunPython(backfill_correction_arxiv_category, migrations.RunPython.noop)]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest ../../wjs-submission-project/tests/test_correction.py -v`
Expected: all PASS.

- [ ] **Step 6: Check migration graph**

Run (from `janeway/src`): `python manage.py makemigrations wjs_submission --check --dry-run`
Expected: "No changes detected".
Run: `python manage.py migrate wjs_submission --plan | tail -5`
Expected: `wjs_submission.0024_backfill_correction_arxiv_category` listed (or already applied
after an actual `migrate`), with no graph errors.

- [ ] **Step 7: Lint**

Run (from wjs-submission-project): `pre-commit run --files wjs/plugins/wjs_submission/data.py wjs/plugins/wjs_submission/migrations/0024_backfill_correction_arxiv_category.py wjs/plugins/wjs_submission/correction/logic.py tests/test_correction.py`
Expected: all hooks pass.

- [ ] **Step 8: Commit (only if per-change commits were chosen in flow step 4)**

```bash
git add wjs/plugins/wjs_submission/data.py wjs/plugins/wjs_submission/migrations/0024_backfill_correction_arxiv_category.py tests/test_correction.py
git commit -m "fix: backfill arXiv category on existing errata and addenda (#3212)"
```

---

### Final verification

- [ ] Run the full suite (from `janeway/src`): `pytest -n7 ../../wjs-submission-project`
  Expected: no new failures compared with `wjs-develop`.
