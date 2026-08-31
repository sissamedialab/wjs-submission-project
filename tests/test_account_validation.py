"""
Tests for the correspondence-author validators in account_validation.py.

jcom_correspondence_author_validation and jcap_correspondence_author_validation moved to
wjs.jcom_profile.account_validation (see wjs-submission-project#30): wjs-submission must not
depend on wjs.jcom_profile. Their tests moved to wjs-profile-project's
wjs/jcom_profile/tests/test_account_validation.py.
"""

import pytest
from core.models import Account
from plugins.wjs_submission.account_validation import default_correspondence_author_validation


def _reload(user: Account) -> Account:
    """Return a fresh Account instance with no cached related objects."""
    return Account.objects.get(pk=user.pk)


@pytest.mark.django_db
def test_default_correspondence_author_validation_valid_user_passes(user: Account):
    """The `user` fixture already has a name, an email, is active and has an institution."""
    assert default_correspondence_author_validation(user), "a fully-completed profile should validate"


@pytest.mark.django_db
def test_default_correspondence_author_validation_inactive_user_fails(user: Account):
    Account.objects.filter(pk=user.pk).update(is_active=False)
    assert not default_correspondence_author_validation(_reload(user)), "an inactive user must not validate"


@pytest.mark.django_db
def test_default_correspondence_author_validation_missing_names_fails(user: Account):
    Account.objects.filter(pk=user.pk).update(first_name="", last_name="")
    assert not default_correspondence_author_validation(_reload(user)), (
        "a user without first_name nor last_name must not validate"
    )


@pytest.mark.django_db
def test_default_correspondence_author_validation_missing_email_fails(user: Account):
    Account.objects.filter(pk=user.pk).update(email="")
    assert not default_correspondence_author_validation(_reload(user)), "a user without an email must not validate"


@pytest.mark.django_db
def test_default_correspondence_author_validation_missing_institution_fails(user: Account):
    user.affiliations.all().delete()
    assert not default_correspondence_author_validation(_reload(user)), (
        "a user without an institution must not validate"
    )
