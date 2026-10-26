"""Tests for the correction (erratum/addendum) submission workflow."""

from collections.abc import Callable, Iterator
from unittest.mock import MagicMock, patch

import pytest
from core.models import Account
from submission.models import (
    Article,
    FrozenAuthor,
    Licence,
    Section,
)

# The correction workflow writes links through the hydra plugin. Skip this whole
# module when the plugin is not installed in the current test environment.
hydra_models = pytest.importorskip("plugins.hydra.models", reason="hydra plugin not installed")

from plugins.wjs_submission.access_mode import (  # noqa: E402
    get_access_mode_configuration,
)
from plugins.wjs_submission.correction.logic import (  # noqa: E402
    ADDENDUM,
    ERRATUM,
    SetupCorrectionStorage,
    get_correction_title,
)
from plugins.wjs_submission.models import AccessMode, AccessModeJournal, ArticleSubmission  # noqa: E402
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
    assert (
        FrozenAuthor.objects.filter(article=to_article).count()
        == FrozenAuthor.objects.filter(article=published_article_with_frozen_authors).count()
    )


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


@pytest.fixture
def free_to_read_correction_settings(journal) -> Iterator[AccessMode]:
    """
    Configure the journal under test to publish corrections as "Free to read".

    Yields:
        The "Free to read" access mode.

    """
    access_mode = AccessMode.objects.create(name="Free to read", code="free-to-read", user_selectable=False)
    with patch(
        "plugins.wjs_submission.access_mode.CORRECTION_ACCESS_MODE_CODE",
        {None: "open-access", journal.code: "free-to-read"},
    ):
        yield access_mode


@pytest.fixture
def original_licence_and_rights(published_article: Article) -> tuple[Licence, str]:
    """Give the published article a licence and rights different from the open-access preset."""
    licence = Licence.objects.create(journal=published_article.journal, short_name="most-rights", name="most-rights")
    published_article.license = licence
    published_article.rights = "Publisher"
    published_article.save()
    return licence, "Publisher"


@pytest.mark.django_db
def test_correction_default_access_mode_keeps_original_licence_and_rights(
    published_article_with_frozen_authors: Article,
    original_licence_and_rights: tuple[Licence, str],
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """Without a per-journal override the correction is open access, keeping licence and rights of the original."""
    to_article = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    ).run()
    licence, rights = original_licence_and_rights
    preset = AccessModeJournal.objects.get(access_mode__code="open-access", journal=to_article.journal)
    assert preset.copyright != rights, "the original rights must differ from the preset for the test to be meaningful"
    assert to_article.submission_data.access_mode.code == "open-access", "default access mode must be open access"
    assert to_article.license == licence, "licence must be the original one, not the open-access preset"
    assert to_article.rights == rights, "rights must be the original ones, not the open-access preset"


@pytest.mark.django_db
def test_correction_free_to_read_inherits_licence_and_rights(
    published_article_with_frozen_authors: Article,
    original_licence_and_rights: tuple[Licence, str],
    free_to_read_correction_settings: AccessMode,
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """A correction in a "free to read" journal copies licence and rights from the original article."""
    to_article = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    ).run()
    licence, rights = original_licence_and_rights
    assert to_article.submission_data.access_mode == free_to_read_correction_settings
    assert to_article.license == licence
    assert to_article.rights == rights


@pytest.mark.django_db
def test_correction_free_to_read_ignores_journal_preset(
    published_article_with_frozen_authors: Article,
    original_licence_and_rights: tuple[Licence, str],
    free_to_read_correction_settings: AccessMode,
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """The journal preset of the "free to read" access mode does not override the original article data."""
    AccessModeJournal.objects.create(
        access_mode=free_to_read_correction_settings,
        journal=published_article_with_frozen_authors.journal,
        licence=Licence.objects.get(short_name="CC BY 4.0", journal=published_article_with_frozen_authors.journal),
        copyright="Authors",
    )
    to_article = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    ).run()
    licence, rights = original_licence_and_rights
    assert to_article.license == licence
    assert to_article.rights == rights


@pytest.mark.django_db
def test_correction_missing_access_mode_raises(
    published_article_with_frozen_authors: Article,
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """A configured but missing access mode is an error, not silently ignored."""
    with patch("plugins.wjs_submission.access_mode.CORRECTION_ACCESS_MODE_CODE", {None: "does-not-exist"}):
        setup = SetupCorrectionStorage(
            article_id=published_article_with_frozen_authors.id,
            relationship=ERRATUM,
            request=MagicMock(user=request_user),
        )
        with pytest.raises(AccessMode.DoesNotExist):
            setup.run()


@pytest.mark.django_db
def test_correction_configuration_uses_correction_data(
    published_article_with_frozen_authors: Article,
    original_licence_and_rights: tuple[Licence, str],
    free_to_read_correction_settings: AccessMode,
    request_user: Account,
    erratum_section: Section,
    install_plugins: Callable,
):
    """The step 7 configuration of a correction is fixed and built from the correction itself."""
    to_article = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    ).run()
    configuration = get_access_mode_configuration(request_user, to_article)
    licence, rights = original_licence_and_rights
    assert configuration.access_mode == free_to_read_correction_settings
    assert configuration.license == licence
    assert configuration.copyright_text == rights
    assert configuration.user_can_select_access_mode is False


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
    # ArticleSubmission is created by a post_save signal on Article.
    ArticleSubmission.objects.filter(article=published_article_with_frozen_authors).update(
        arxiv_category="astro-ph.CO"
    )
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
    """A corrected article without ArticleSubmission (legacy data) leaves the correction's category empty."""
    ArticleSubmission.objects.filter(article=published_article_with_frozen_authors).delete()
    setup = SetupCorrectionStorage(
        article_id=published_article_with_frozen_authors.id,
        relationship=ERRATUM,
        request=MagicMock(user=request_user),
    )
    to_article = setup.run()
    to_article.refresh_from_db()
    assert not to_article.submission_data.arxiv_category
