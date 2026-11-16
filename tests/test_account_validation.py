"""
Tests for the correspondence-author rules in account_validation.py.

The per-journal rules are data (`CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS`), evaluated by
`missing_required_fields`; the `*_correspondence_author_validation` functions stay as injection points.
jcom/jcap rules live in wjs.jcom_profile.account_validation (see wjs-submission-project#30): wjs-submission must
not depend on wjs.jcom_profile. Their tests are in wjs-profile-project's
wjs/jcom_profile/tests/test_account_validation.py.
"""

import itertools
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from core.models import Account
from journal.models import Journal
from plugins.wjs_submission.account_validation import (
    default_correspondence_author_validation,
    get_correspondence_author_missing_fields,
    get_required_field_entries,
    is_required_field_entry_satisfied,
    is_user_eligible_for_correspondence_author,
    is_whitelisted_correspondence_author,
    missing_required_fields,
)
from plugins.wjs_submission.models import WhitelistedCorrespondenceAuthors
from plugins.wjs_submission.required_fields_types import RequiredFieldEntry
from plugins.wjs_submission.settings import (
    DEFAULT_CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS,
    DEFAULT_CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION,
)

REQUIRED_FIELDS_SETTING = "plugins.wjs_submission.account_validation.CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS"
VALIDATION_SETTING = "plugins.wjs_submission.account_validation.CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION"


@pytest.fixture
def default_rules():
    """Pin the default rules: installing projects may override them per journal (e.g. wjs-profile-project)."""
    with (
        patch(REQUIRED_FIELDS_SETTING, DEFAULT_CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS),
        patch(VALIDATION_SETTING, DEFAULT_CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION),
    ):
        yield


def _reload(user: Account) -> Account:
    """Return a fresh Account instance with no cached related objects."""
    return Account.objects.get(pk=user.pk)


# -- frozen references: the behavior this refactoring must preserve ----------------------------


def _old_validation(user) -> bool:
    """`default_correspondence_author_validation` as in 23be0c8^ (before the required-fields dict)."""
    is_active = user.is_active
    personal_data = (user.last_name or user.first_name) and user.email
    professional_data = user.institution
    return is_active and personal_data and professional_data


def _old_missing_fields(user) -> list[str]:
    """`default_correspondence_author_missing_fields` as of the branch HEAD before the required-fields dict."""
    missing = []
    if not user.is_active:
        missing.append("Active account")
    if not (user.last_name or user.first_name):
        missing.append("Name")
    if not user.email:
        missing.append("Email")
    if not user.institution:
        missing.append("Affiliation")
    return missing


def _stub_user(**fields) -> SimpleNamespace:
    return SimpleNamespace(**fields)


@pytest.mark.django_db
def test_default_validation_equivalent_to_old_validation(default_rules):
    journal = SimpleNamespace(code="NOT-IN-SETTING")
    combinations = itertools.product((True, False), ("", "A"), ("", "B"), ("", "e@x.org"), ("", "Uni"))
    for is_active, first_name, last_name, email, institution in combinations:
        user = _stub_user(
            is_active=is_active, first_name=first_name, last_name=last_name, email=email, institution=institution
        )
        case = (is_active, first_name, last_name, email, institution)
        assert bool(_old_validation(user)) == default_correspondence_author_validation(user, journal), case
        missing = missing_required_fields(user, journal)
        assert isinstance(missing, list), case
        assert [str(label) for label in missing] == _old_missing_fields(user), case
        assert default_correspondence_author_validation(user, journal) == (not missing), case


# -- missing_required_fields: entry evaluation -------------------------------------------------


def _entries_user(**attrs) -> SimpleNamespace:
    return SimpleNamespace(**attrs)


@pytest.mark.django_db
def test_missing_required_fields_any_of_paths_truthy():
    rules = {None: [{"label": "Name", "paths": ["last_name", "first_name"]}]}
    journal = SimpleNamespace(code="X")
    with patch(REQUIRED_FIELDS_SETTING, rules):
        assert missing_required_fields(_entries_user(first_name="A", last_name=""), journal) == []
        assert missing_required_fields(_entries_user(first_name="", last_name="B"), journal) == []
        assert missing_required_fields(_entries_user(first_name="", last_name=""), journal) == ["Name"]


@pytest.mark.django_db
def test_missing_required_fields_allowed_values_membership_not_truthiness():
    rules = {None: [{"label": "Profession", "paths": ["profile.profession"], "allowed": {"0", "1"}}]}
    journal = SimpleNamespace(code="X")
    with patch(REQUIRED_FIELDS_SETTING, rules):
        for value, expected in (
            ("0", []),
            ("1", []),
            ("", ["Profession"]),
            (None, ["Profession"]),
            ("9", ["Profession"]),
        ):
            user = _entries_user(profile=SimpleNamespace(profession=value))
            assert missing_required_fields(user, journal) == expected, value


@pytest.mark.django_db
def test_missing_required_fields_calls_callables_and_keeps_dict_order():
    rules = {None: [{"label": "B", "paths": ["b"]}, {"label": "A", "paths": ["a"]}, {"label": "C", "paths": ["c"]}]}
    journal = SimpleNamespace(code="X")
    user = _entries_user(a=lambda: "", b=lambda: None, c=lambda: "ok")
    with patch(REQUIRED_FIELDS_SETTING, rules):
        assert missing_required_fields(user, journal) == ["B", "A"]


@pytest.mark.django_db
def test_missing_required_fields_journal_entry_or_none_fallback():
    rules = {
        "JX": [{"label": "Only JX", "paths": ["x"]}],
        None: [{"label": "Fallback", "paths": ["y"]}],
    }
    user = _entries_user(x="", y="")
    with patch(REQUIRED_FIELDS_SETTING, rules):
        assert missing_required_fields(user, SimpleNamespace(code="JX")) == ["Only JX"]
        assert missing_required_fields(user, SimpleNamespace(code="OTHER")) == ["Fallback"]


# -- default validation on real accounts -------------------------------------------------------


@pytest.mark.django_db
def test_default_validation_valid_user_passes(default_rules, journal: Journal, user: Account):
    """The `user` fixture already has a name, an email, is active and has an institution."""
    assert default_correspondence_author_validation(user, journal), "a fully-completed profile should validate"


@pytest.mark.django_db
def test_default_validation_inactive_user_fails(default_rules, journal: Journal, user: Account):
    Account.objects.filter(pk=user.pk).update(is_active=False)
    assert not default_correspondence_author_validation(_reload(user), journal), "an inactive user must not validate"
    assert [str(f) for f in missing_required_fields(_reload(user), journal)] == ["Active account"]


@pytest.mark.django_db
def test_default_validation_missing_names_and_email_fail(default_rules, journal: Journal, user: Account):
    Account.objects.filter(pk=user.pk).update(first_name="", last_name="", email="")
    assert not default_correspondence_author_validation(_reload(user), journal)
    assert [str(f) for f in missing_required_fields(_reload(user), journal)] == ["Name", "Email"]


@pytest.mark.django_db
def test_default_validation_missing_institution_fails(default_rules, journal: Journal, user: Account):
    user.affiliations.all().delete()
    assert not default_correspondence_author_validation(_reload(user), journal)
    assert [str(f) for f in missing_required_fields(_reload(user), journal)] == ["Affiliation"]


# -- eligibility / step 4 ----------------------------------------------------------------------


@pytest.mark.django_db
def test_eligibility_valid_user(default_rules, journal: Journal, user: Account):
    assert is_user_eligible_for_correspondence_author(journal, user)


@pytest.mark.django_db
def test_eligibility_incomplete_user_not_eligible(default_rules, journal: Journal, user: Account):
    user.affiliations.all().delete()
    assert not is_user_eligible_for_correspondence_author(journal, _reload(user))


@pytest.mark.django_db
def test_eligibility_whitelisted_user_is_eligible(default_rules, journal: Journal, user: Account):
    user.affiliations.all().delete()
    WhitelistedCorrespondenceAuthors.objects.create(user=user, journal=journal)
    assert is_user_eligible_for_correspondence_author(journal, _reload(user))


@pytest.mark.django_db
def test_eligibility_uses_injected_validation_function_with_user_and_journal(
    default_rules, journal: Journal, user: Account
):
    user.affiliations.all().delete()  # invalid according to the dict
    calls = []

    def injected(user, journal):
        calls.append((user, journal))
        return True

    with (
        patch(VALIDATION_SETTING, {None: "tests.test_account_validation._injected_validation"}),
        patch("tests.test_account_validation._injected_validation", injected, create=True),
    ):
        assert is_user_eligible_for_correspondence_author(journal, _reload(user))
    assert [(u.pk, j.pk) for u, j in calls] == [(user.pk, journal.pk)]


@pytest.mark.django_db
def test_get_missing_fields_uses_journal_rules(default_rules, journal: Journal, user: Account):
    user.affiliations.all().delete()
    missing = get_correspondence_author_missing_fields(journal, _reload(user))
    assert [str(field) for field in missing] == ["Affiliation"]


@pytest.mark.django_db
def test_get_missing_fields_whitelisted_user(default_rules, journal: Journal, user: Account):
    user.affiliations.all().delete()
    WhitelistedCorrespondenceAuthors.objects.create(user=user, journal=journal)
    assert get_correspondence_author_missing_fields(journal, _reload(user)) == []


# -- public helpers over the dict --------------------------------------------------------------


@pytest.mark.django_db
def test_get_required_field_entries_journal_or_none_fallback():
    rules = {"JX": [{"label": "Only JX", "paths": ["x"]}], None: [{"label": "Fallback", "paths": ["y"]}]}
    with patch(REQUIRED_FIELDS_SETTING, rules):
        assert get_required_field_entries(SimpleNamespace(code="JX")) == rules["JX"]
        assert get_required_field_entries(SimpleNamespace(code="OTHER")) == rules[None]


@pytest.mark.django_db
def test_is_required_field_entry_satisfied_any_of_and_allowed():
    any_of = {"label": "Name", "paths": ["last_name", "first_name"]}
    allowed = {"label": "Profession", "paths": ["profile.profession"], "allowed": [0, 1]}
    user = SimpleNamespace(last_name="", first_name="A", profile=SimpleNamespace(profession=0))
    assert is_required_field_entry_satisfied(user, any_of)
    assert is_required_field_entry_satisfied(user, allowed), "0 is an allowed value, not a falsy one"
    empty = SimpleNamespace(last_name="", first_name="", profile=SimpleNamespace(profession=None))
    assert not is_required_field_entry_satisfied(empty, any_of)
    assert not is_required_field_entry_satisfied(empty, allowed)


@pytest.mark.django_db
def test_is_whitelisted_correspondence_author_public(journal: Journal, user: Account):
    assert not is_whitelisted_correspondence_author(journal, user)
    WhitelistedCorrespondenceAuthors.objects.create(user=user, journal=journal)
    assert is_whitelisted_correspondence_author(journal, user)


def assert_entries_match_typed_dict(rules: dict, entry_type) -> None:
    """Every entry of a journal -> entries dict has all required keys and no key unknown to `entry_type`."""
    known = entry_type.__required_keys__ | entry_type.__optional_keys__
    for journal_code, entries in rules.items():
        for entry in entries:
            assert entry_type.__required_keys__ <= entry.keys(), (journal_code, entry)
            assert entry.keys() <= known, (journal_code, entry, "unknown keys: %s" % (entry.keys() - known))


@pytest.mark.django_db
def test_default_required_fields_entries_match_the_typed_dict():
    assert RequiredFieldEntry.__required_keys__ == {"label", "paths"}
    assert RequiredFieldEntry.__optional_keys__ == {"allowed"}
    assert_entries_match_typed_dict(DEFAULT_CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS, RequiredFieldEntry)
