from collections.abc import Callable

import pytest
from django.contrib.auth import get_user_model
from django.core import management
from django.urls.base import clear_script_prefix, clear_url_caches, set_script_prefix
from journal.models import Journal
from press.models import Press
from utils.install import update_emails, update_issue_types, update_settings, update_xsl_files

Account = get_user_model()


JOURNAL_CODE = "JCOM"


@pytest.fixture
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
    press: Press,  # noqa: ARG001
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
def journal(press: Press) -> Journal:
    """Prepare a journal."""
    journal = _journal_factory(JOURNAL_CODE, press, domain="testserver.org")
    # This injects current journal code as prefix for all URLs in the current thread, ensuring reverse correctly
    # generates URLs with the journal code as prefix
    # This is the same code run by `core.middleware.SiteSettingsMiddleware` ensuring the same behavior in the tests
    set_script_prefix(f"/{journal.code}")
    return journal


# TODO: refactor into fixture "press"?
@pytest.fixture(autouse=True)
def journal_config(settings: Callable):
    """
    Ensure use the "path" URL_CONFIG variant is used.

    This fixture ensures that setting is coherent with the current test configuration.
    """
    settings.URL_CONFIG = "path"


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


@pytest.fixture
def admin() -> Account:
    """Create admin user."""
    admin, _ = Account.objects.get_or_create(
        username="admin@invalid.com",
        email="admin@invalid.com",
        first_name="Admin",
        last_name="Admin",
        is_active=True,
        is_staff=True,
        is_admin=True,
        is_superuser=True,
    )
    return admin
