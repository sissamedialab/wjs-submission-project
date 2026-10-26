"""Table of the access mode / licence / rights rules applied by ``get_access_mode_configuration``."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest
from core.models import Account
from plugins.wjs_submission.access_mode import (
    AccessModeConfiguration,
    get_access_mode_configuration,
    get_correction_access_mode,
)
from plugins.wjs_submission.models import AccessMode, RevisionStorage
from plugins.wjs_submission.settings import OA_CODE
from submission.models import Article, Licence

CONTROL_FUNCTION = "plugins.wjs_submission.access_mode.import_string"


@pytest.fixture
def stored_values(article: Article, user: Account) -> tuple[Article, AccessMode, Licence]:
    """Article with a stored access mode, a custom licence and rights, and an affiliation."""
    access_mode = AccessMode.objects.exclude(code=OA_CODE).first()
    licence = Licence.objects.create(short_name="original", name="Original", journal=article.journal)
    article.license = licence
    article.rights = "original rights"
    article.save()
    article.submission_data.affiliation = user.primary_affiliation()
    article.submission_data.access_mode = access_mode
    article.submission_data.license_override = True
    article.submission_data.rights_override = True
    article.submission_data.save()
    return article, access_mode, licence


@pytest.fixture
def calculated() -> AccessModeConfiguration:
    """Return what the journal control function calculates, always different from the stored values."""
    oa = AccessMode.objects.get(code=OA_CODE)
    return AccessModeConfiguration(
        access_mode=oa, license=None, copyright_text="calculated", user_can_select_access_mode=True
    )


def _article_configuration(access_mode: AccessMode, licence: Licence) -> AccessModeConfiguration:
    return AccessModeConfiguration(
        access_mode=access_mode, license=licence, copyright_text="original rights", user_can_select_access_mode=False
    )


def _create_revision(article: Article, flow_type: str, *, changed: str | None = None) -> RevisionStorage:
    """Revision storage holding the corresponding author and affiliation, optionally changed."""
    data = {
        "correspondence_author": article.correspondence_author.pk,
        "affiliation_pk": article.submission_data.affiliation_id,
    }
    if changed == "affiliation":
        data["affiliation_pk"] = None
    elif changed == "author":
        data["correspondence_author"] = article.correspondence_author.pk + 1000
    return RevisionStorage.objects.create(article=article, revision_flow_type=flow_type, data=data)


@pytest.mark.django_db
def test_policy_plain_submission_uses_control_function(
    stored_values, calculated: AccessModeConfiguration, user: Account, install_plugins: Callable
):
    """A plain submission always gets the result of the journal control function."""
    article, __, __ = stored_values
    with patch(CONTROL_FUNCTION, return_value=lambda user, article: calculated):
        assert get_access_mode_configuration(user, article) == calculated


@pytest.mark.django_db
def test_policy_correction_returns_article_values(
    stored_values, calculated: AccessModeConfiguration, user: Account, install_plugins: Callable
):
    """A correction is fixed to the values set up at creation, the control function is not even called."""
    article, access_mode, licence = stored_values
    control_function = MagicMock(return_value=calculated)
    with (
        patch("plugins.wjs_submission.access_mode.is_correction", return_value=True),
        patch(CONTROL_FUNCTION, return_value=control_function),
    ):
        configuration = get_access_mode_configuration(user, article)
    assert configuration == _article_configuration(access_mode, licence)
    control_function.assert_not_called()


@pytest.mark.parametrize("flow_type", RevisionStorage.RevisionFlowType.values)
@pytest.mark.django_db
def test_policy_revision_unchanged_returns_article_values(
    stored_values,
    calculated: AccessModeConfiguration,
    user: Account,
    install_plugins: Callable,
    flow_type: str,
):
    """Without author and affiliation changes the article values are kept, whatever the revision type."""
    article, access_mode, licence = stored_values
    _create_revision(article, flow_type)
    with patch(CONTROL_FUNCTION, return_value=lambda user, article: calculated):
        assert get_access_mode_configuration(user, article) == _article_configuration(access_mode, licence)


@pytest.mark.django_db
def test_policy_revision_unchanged_keeps_not_selectable_access_mode(
    stored_values, calculated: AccessModeConfiguration, user: Account, install_plugins: Callable
):
    """A stored access mode that authors cannot choose (e.g. free to read) is kept and not selectable."""
    article, access_mode, __ = stored_values
    access_mode.user_selectable = False
    access_mode.save()
    _create_revision(article, RevisionStorage.RevisionFlowType.FULL)
    with patch(CONTROL_FUNCTION, return_value=lambda user, article: calculated):
        configuration = get_access_mode_configuration(user, article)
    assert configuration.access_mode == access_mode
    assert configuration.user_can_select_access_mode is False


@pytest.mark.parametrize("changed", ["affiliation", "author"])
@pytest.mark.django_db
def test_policy_revision_changed_uses_control_function(
    stored_values, calculated: AccessModeConfiguration, user: Account, install_plugins: Callable, changed: str
):
    """If author or affiliation change in the revision the access mode is recalculated as for a plain submission."""
    article, __, __ = stored_values
    _create_revision(article, RevisionStorage.RevisionFlowType.FULL, changed=changed)
    with patch(CONTROL_FUNCTION, return_value=lambda user, article: calculated):
        assert get_access_mode_configuration(user, article) == calculated


@pytest.mark.django_db
def test_policy_revision_without_stored_access_mode_uses_control_function(
    stored_values, calculated: AccessModeConfiguration, user: Account, install_plugins: Callable
):
    """There is nothing to preserve if the article has no access mode."""
    article, __, __ = stored_values
    article.submission_data.access_mode = None
    article.submission_data.save()
    _create_revision(article, RevisionStorage.RevisionFlowType.FULL)
    with patch(CONTROL_FUNCTION, return_value=lambda user, article: calculated):
        assert get_access_mode_configuration(user, article) == calculated


@pytest.mark.parametrize(
    ("journal_code", "expected_code"),
    [
        ("JCAP", "free-to-read"),
        ("JSTAT", "free-to-read"),
        ("JINST", "free-to-read"),
        ("JCOM", OA_CODE),
        ("JHEP", OA_CODE),
    ],
)
@pytest.mark.django_db
def test_policy_correction_access_mode_per_journal(
    journal_code: str, expected_code: str, journal, install_plugins: Callable
):
    """Corrections of JCAP, JSTAT and JINST are free to read, all other journals are open access."""
    AccessMode.objects.get_or_create(code="free-to-read", defaults={"name": "Free to read", "user_selectable": False})
    settings = {None: OA_CODE, "JCAP": "free-to-read", "JSTAT": "free-to-read", "JINST": "free-to-read"}
    with patch("plugins.wjs_submission.access_mode.CORRECTION_ACCESS_MODE_CODE", settings):
        journal = MagicMock(code=journal_code)
        assert get_correction_access_mode(journal).code == expected_code
