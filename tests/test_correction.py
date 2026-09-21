"""Tests for the correction (erratum/addendum) submission workflow."""

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from core.models import Account
from submission.models import (
    Article,
    FrozenAuthor,
    Section,
)

# The correction workflow writes links through the hydra plugin. Skip this whole
# module when the plugin is not installed in the current test environment.
hydra_models = pytest.importorskip("plugins.hydra.models", reason="hydra plugin not installed")

from plugins.wjs_submission.correction.logic import (  # noqa: E402
    ADDENDUM,
    ERRATUM,
    SetupCorrectionStorage,
    get_correction_title,
)
from plugins.wjs_submission.workflow import is_correction  # noqa: E402

from tests.conftest import _user  # noqa: E402

LinkedArticle = hydra_models.LinkedArticle


@pytest.fixture
def erratum_section(journal) -> Section:
    """Create an Erratum section for the journal."""
    return Section.objects.create(journal=journal, name="Erratum", public_submissions=True)


@pytest.fixture
def addendum_section(journal) -> Section:
    """Create an Addendum section for the journal."""
    return Section.objects.create(journal=journal, name="Addendum", public_submissions=True)


@pytest.fixture
def published_article_with_frozen_authors(published_article, author, coauthor) -> Article:
    """Create FrozenAuthor records for the published article."""
    FrozenAuthor.objects.create(
        article=published_article,
        author=author,
        first_name="Test",
        last_name="Author",
        order=0,
    )
    FrozenAuthor.objects.create(
        article=published_article,
        author=coauthor,
        first_name="Test",
        last_name="Coauthor",
        order=1,
    )
    return published_article


@pytest.mark.django_db
def test_is_correction_false_for_none():
    """Return False when article is None."""
    assert is_correction(None) is False


@pytest.mark.django_db
def test_is_correction_false_for_regular_article(article: Article):
    """Return False for a regular article without a hydra link or correction section."""
    assert is_correction(article) is False


@pytest.mark.django_db
def test_is_correction_false_for_article_with_hydra_link_but_wrong_section(
    article: Article,
    published_article: Article,
):
    """Return False when article has a hydra link but section is not Erratum/Addendum."""
    LinkedArticle.objects.create(
        from_article=published_article,
        to_article=article,
        relationship="correction",
    )
    # article's section is "section0", not Erratum/Addendum
    assert is_correction(article) is False


@pytest.mark.django_db
def test_is_correction_true_for_erratum_with_hydra_link(
    article: Article,
    published_article: Article,
    erratum_section: Section,
):
    """Return True when article has a hydra link with relationship erratum and section is Erratum."""
    article.section = erratum_section
    article.save()
    LinkedArticle.objects.create(
        from_article=published_article,
        to_article=article,
        relationship="erratum",
    )
    assert is_correction(article) is True


@pytest.mark.django_db
def test_first_erratum_title(published_article: Article):
    """Build the title for the first erratum: 'ERRATUM: original.title'."""
    title = get_correction_title(published_article, ERRATUM)
    assert title == f"ERRATUM: {published_article.title}"


@pytest.mark.django_db
def test_first_addendum_title(published_article: Article):
    """Build the title for the first addendum: 'ADDENDUM: original.title'."""
    title = get_correction_title(published_article, ADDENDUM)
    assert title == f"ADDENDUM: {published_article.title}"


@pytest.mark.django_db
def test_second_erratum_title(
    published_article: Article,
    article: Article,
    erratum_section: Section,
):
    """Build the title for the second erratum: 'ERRATUM2: original.title'."""
    # The existing child must be in the Erratum section for the count to work.
    article.section = erratum_section
    article.save()
    LinkedArticle.objects.create(
        from_article=published_article,
        to_article=article,
        relationship="erratum",
    )
    title = get_correction_title(published_article, ERRATUM)
    assert title == f"ERRATUM2: {published_article.title}"


@pytest.mark.django_db
def test_setup_correction_conditions_published(
    published_article: Article,
    request_user: Account,
    install_plugins: Callable,
):
    """Check that _check_conditions returns True for a published article with author user."""
    setup = SetupCorrectionStorage(
        article_id=published_article.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    )
    setup.from_article = published_article
    assert setup._check_conditions(published_article) is True  # noqa: SLF001


@pytest.mark.django_db
def test_setup_correction_conditions_unpublished(
    article: Article,
    request_user: Account,
    install_plugins: Callable,
):
    """Check that _check_conditions returns False for an unsubmitted article."""
    setup = SetupCorrectionStorage(
        article_id=article.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    )
    setup.from_article = article
    assert setup._check_conditions(article) is False  # noqa: SLF001


@pytest.mark.django_db
def test_setup_correction_conditions_non_author(
    published_article: Article,
    coauthor: Account,
    install_plugins: Callable,
):
    """Check that _check_conditions returns False when user is not an author."""
    # coauthor is actually a coauthor of the article, so this should pass.
    # Let's use a completely unrelated user instead.

    unrelated_user = _user("unrelated", False)
    setup = SetupCorrectionStorage(
        article_id=published_article.id,
        relationship=ERRATUM,
        request=MagicMock(user=unrelated_user),
    )
    setup.from_article = published_article
    assert setup._check_conditions(published_article) is False  # noqa: SLF001


@pytest.mark.django_db
def test_run_raises_for_unpublished(
    article: Article,
    request_user: Account,
    install_plugins: Callable,
):
    """Raise ValueError when attempting to start a correction for an unpublished article."""
    setup = SetupCorrectionStorage(
        article_id=article.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    )
    with pytest.raises(ValueError, match="Cannot start a correction"):
        setup.run()


@pytest.mark.django_db
def test_run_creates_correction_article(
    published_article_with_frozen_authors: Article,
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """Create a correction article with correct stage, owner, section, and pre-populated metadata."""
    setup = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    )
    to_article = setup.run()
    assert to_article.owner == request_user
    assert to_article.journal == published_article_with_frozen_authors.journal
    assert to_article.section.name == "Erratum"
    assert to_article.title.startswith("ERRATUM:")
    assert not to_article.abstract
    # Verify FrozenAuthor records were copied.
    assert FrozenAuthor.objects.filter(article=to_article).count() == 2


@pytest.mark.django_db
def test_run_creates_hydra_link(
    published_article_with_frozen_authors: Article,
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """After run(), a LinkedArticle with the correct relationship is created."""
    setup = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    )
    to_article = setup.run()
    link = LinkedArticle.objects.get(
        from_article=published_article_with_frozen_authors,
        to_article=to_article,
    )
    assert link.relationship == "erratum"


@pytest.mark.django_db
def test_run_twice_does_not_corrupt_article(
    published_article_with_frozen_authors: Article,
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """Call setup.run() twice and verify the title and author count are not corrupted on resume."""
    request_mock = MagicMock(user=request_user)

    # First run: creates the correction and the hydra LinkedArticle.
    setup1 = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=request_mock,
    )
    to_article1 = setup1.run()
    original_title = to_article1.title
    original_author_count = FrozenAuthor.objects.filter(article=to_article1).count()

    # The first run() must have created the LinkedArticle for the resume to work.
    assert LinkedArticle.objects.filter(
        from_article=published_article_with_frozen_authors,
        to_article=to_article1,
        relationship=ERRATUM,
    ).exists()

    # Second run: resumes the existing correction found via the hydra link.
    setup2 = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=request_mock,
    )
    to_article2 = setup2.run()

    # Should return the same article.
    assert to_article2.pk == to_article1.pk
    # Title should not change (no ERRATUM2 on resume).
    assert to_article2.title == original_title
    # Author count should not double.
    assert FrozenAuthor.objects.filter(article=to_article2).count() == original_author_count
