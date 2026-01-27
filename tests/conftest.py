import random
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from core.models import File, SupplementaryFile
from django.apps import apps
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core import management
from django.urls.base import clear_script_prefix, clear_url_caches, set_script_prefix
from django.utils import translation
from django.utils.timezone import now
from journal.models import Journal
from plugins.wjs_submission import constants
from plugins.wjs_submission.arxiv import fetch_arxiv_metadata
from plugins.wjs_submission.data import create_access_mode
from plugins.wjs_submission.models import AccessMode
from plugins.wjs_submission.settings import OA_CODE
from press.models import Press
from submission import models as submission_models
from submission.models import Article, Licence
from utils.install import (
    update_emails,
    update_issue_types,
    update_settings,
    update_xsl_files,
)
from utils.management.commands.install_janeway import ROLES_RELATIVE_PATH

from .helpers import DummyResponse, mock_requests_get
from .utils import create_rich_fake_request

Account = get_user_model()


JOURNAL_CODE = "JCOM"


@pytest.fixture(autouse=True)
def install_plugins():
    management.call_command("install_plugins")


def set_general_settings():
    """Define default settings to replace data defined in datamigration."""
    # general settings must be defined before journal creation
    if not Journal.objects.all().exists():
        update_xsl_files()
        update_settings()
        update_emails()


@pytest.fixture
def press() -> Press:
    """Prepare a press."""
    # Copied from journal.tests.test_models
    # which theme??? apress.theme = "JCOM-theme"; press.save()
    return Press.objects.create(domain="testserver", is_secure=False, name="Medialab")


def _journal_factory(
    code: str,
    press: Press,
    domain: str | None = None,
) -> Journal:
    """Create a journal initializing its settings."""
    domain = domain or f"{code}.testserver.org"
    set_general_settings()
    journal = Journal.objects.create(code=code, domain=domain)
    journal.title = f"Journal {code}: A journal of tests"
    journal.save()
    update_issue_types(journal)
    return journal


@pytest.fixture
def journal(press: Press, roles) -> Journal:
    """Prepare a journal."""
    journal = _journal_factory(JOURNAL_CODE, press, domain="testserver.org")
    # This injects current journal code as prefix for all URLs in the current thread, ensuring reverse correctly
    # generates URLs with the journal code as prefix
    # This is the same code run by `core.middleware.SiteSettingsMiddleware` ensuring the same behavior in the tests
    set_script_prefix(f"/{journal.code}")
    create_access_mode(apps=apps, schema_editor=None)
    AccessMode.objects.filter(code=OA_CODE).update(user_selectable=False)
    return journal


@pytest.fixture(autouse=True)
def journal_config(settings: Callable):
    """
    Ensure use the "path" URL_CONFIG variant is used.

    This fixture ensures that setting is coherent with the current test configuration.
    """
    settings.URL_CONFIG = "path"


@pytest.fixture
def roles():
    roles_path = Path(django_settings.BASE_DIR) / ROLES_RELATIVE_PATH
    management.call_command("loaddata", roles_path)


@pytest.fixture
def hierarchical_keywords(journal):
    """Set journal to use hierarchical keywords."""
    journal.submissionconfiguration.hierarchical_keywords = True
    journal.submissionconfiguration.autocomplete_keywords = True
    journal.submissionconfiguration.save()


@pytest.fixture
def jquant_journal(press, roles) -> Journal:
    """Create a journal with code JQUANT for tests."""
    journal = _journal_factory("JQUANT", press, domain="jquant.testserver.org")
    set_script_prefix(f"/{journal.code}")
    journal.submissionconfiguration.hierarchical_keywords = True
    journal.submissionconfiguration.autocomplete_keywords = True
    journal.submissionconfiguration.save()
    return journal


@pytest.fixture
def jhep_journal(press, roles) -> Journal:
    """Create a journal with code JHEP for tests."""
    journal = _journal_factory("JHEP", press, domain="jhep.testserver.org")
    set_script_prefix(f"/{journal.code}")
    journal.submissionconfiguration.hierarchical_keywords = True
    journal.submissionconfiguration.autocomplete_keywords = True
    journal.submissionconfiguration.save()
    return journal


@pytest.fixture(autouse=True)
def clear_script_prefix_fix():
    """
    Clear django's script prefix at the end of the test.

    Many tests rely on implicit journal prefix injection done by `core.middleware.SiteSettingsMiddleware`
    which is currently propagated to any test

    ```python
    Set the script prefix if the site is in path mode
    if site_path:
        prefix = "/" + site_path
        logger.debug("Setting script prefix to %s" % prefix)
        set_script_prefix(prefix)
        request.path_info = request.path_info[len(prefix):]
    ```
    This code use django `set_script_prefix` to automatically set the journal code as prefix for all the URLs in the
    current thread. At runtime this is not a problem because the middleware is run on every request and the prefix is
    then set on every run for the current journal.

    As the tests are run by "reusing" the threads (either a single thread when not in parallel mode or a limited set of
    threads in parallel mode) the prefix leaks from one test to another.

    This fixture clears the script prefix before and after the test.
    """
    clear_url_caches()
    clear_script_prefix()
    yield None
    clear_script_prefix()
    clear_url_caches()


def _user(name: str = "user", admin_flag: bool = False) -> Account:
    """Create generic user."""
    user, _ = Account.objects.get_or_create(
        username=f"{name}@invalid.com",
        email=f"{name}@invalid.com",
        first_name="name",
        last_name="name",
        is_active=True,
        is_staff=admin_flag,
        is_admin=admin_flag,
        is_superuser=admin_flag,
    )
    user.set_password("password")
    user.save()
    # FIXME: This is needed to run tests using wjs.defaults.tests (wjs.jcom-profile defaults)
    #  instead of wjs.defaults.tests_submission (wjs-submission defaults) due to the privacy checking middleware
    try:
        user.jcomprofile.gdpr_checkbox = True
        user.jcomprofile.save_base(raw=True)
    except AttributeError:
        pass
    return user


@pytest.fixture
def admin() -> Account:
    """Create admin user."""
    return _user("admin", True)


@pytest.fixture
def user(name: str = "user", admin_flag: bool = False) -> Account:
    return _user(name, admin_flag)


def _article(author, coauthor, journal, sections, submitted=False):
    if submitted:
        date_started = date_submitted = now() - timedelta(
            days=random.randint(10, 20),  # noqa: S311
        )
    else:
        date_started = date_submitted = None
    licence, __ = Licence.objects.get_or_create(
        name="cc-by-nc-nd-4.0", short_name="CC BY-NC-ND 4.0", url="http://example.com", journal=journal
    )
    article = submission_models.Article.objects.create(
        abstract="Abstract",
        journal=journal,
        title="Title",
        correspondence_author=author,
        owner=author,
        date_submitted=date_submitted,
        date_started=date_started,
        section=random.choice(sections),  # noqa: S311
        language="eng",
        license=licence,
    )
    article.authors.add(author, coauthor)
    for file_ext in ["_es.pdf", "_en.pdf", ".epub"]:
        file_obj = File.objects.create(
            original_filename=f"JCOM_0101_2022_R0{article.pk}{file_ext}",
        )
        article.manuscript_files.add(file_obj)
    for file_ext in ["_es.png", "_en.png"]:
        file_obj = File.objects.create(
            original_filename=f"JCOM_0101_2022_R0{article.pk}{file_ext}",
        )
        article.data_figure_files.add(file_obj)
    for file_ext in ["_es.txt", "_en.txt"]:
        file_obj = File.objects.create(
            original_filename=f"JCOM_0101_2022_R0{article.pk}{file_ext}",
        )
        article.supplementary_files.add(SupplementaryFile.objects.create(file=file_obj))
    return article


@pytest.fixture
def sections(journal):
    with translation.override("en"):
        # we must explicitly determine the created sections because sections might be created by other fixtures
        # and returning a blanket "all" queryset would include sections created by those fixtures
        sections_pk = []
        for i in range(3):
            obj = submission_models.Section.objects.create(
                journal=journal,
                name=f"section{i}",
                public_submissions=False,
            )
            sections_pk.append(obj.pk)
    return submission_models.Section.objects.filter(pk__in=sections_pk)


@pytest.fixture
def author(journal: Journal, roles) -> Account:
    user: Account = _user("author", False)
    user.add_account_role(constants.AUTHOR_ROLE, journal)
    return user


@pytest.fixture
def coauthor(journal: Journal, roles) -> Account:
    user: Account = _user("coauthor", False)
    user.add_account_role(constants.AUTHOR_ROLE, journal)
    return user


@pytest.fixture
def article(author, coauthor, journal, sections) -> Article:
    return _article(author, coauthor, journal, sections)


@pytest.fixture
def fake_request(journal, settings):
    """Create a fake_factory request suitable for rendering templates."""
    return create_rich_fake_request(journal, settings)


@pytest.fixture
def arxiv_fixtures() -> dict[str, bytes]:
    """Return a dictionary of files suitable to simulate several arXiv response scenarios."""
    base = Path(__file__).parent / "files"
    return {
        "xml": (base / "query.atom").open("rb").read(),
        "src": (base / "arxiv_tex_sample.tar.gz").open("rb").read(),
        "xml_empty": b"""<feed xmlns="http://www.w3.org/2005/Atom"></feed>""",
    }


@pytest.fixture
def arxiv_metadata(arxiv_fixtures: dict[str, bytes], monkeypatch: Callable):
    """
    Fixture to mock and retrieve ArXiv metadata.

    :param arxiv_fixtures: Dictionary containing byte fixtures for XML and source
      data to be used in mocking ArXiv API responses.
    :type arxiv_fixtures: dict[str, bytes]
    :param monkeypatch: Function used to apply patches for mocking external
      dependencies.
    :type monkeypatch: Callable
    :return: A callable function to fetch and return ArXiv metadata for a given
      ArXiv ID.
    :rtype: Callable[[str], dict]
    :raises RuntimeError: If an error occurs during metadata fetching.
    """

    def inner(arxiv_id: str):
        metadata_resp = DummyResponse(arxiv_fixtures["xml"], status_code=200, text=arxiv_fixtures["xml"].decode())
        src_resp = DummyResponse(arxiv_fixtures["src"])
        mock_requests_get(
            monkeypatch,
            responses={"api/query": metadata_resp, "/src/": src_resp},
        )

        return fetch_arxiv_metadata(arxiv_id)

    return inner
