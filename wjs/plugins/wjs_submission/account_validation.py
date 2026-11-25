from collections.abc import Iterable
from enum import StrEnum

from core.models import Account
from django.db.models import Q
from django.utils import timezone
from django.utils.module_loading import import_string
from journal.models import Journal

from .models import WhitelistedCorrespondenceAuthors
from .required_fields_types import RequiredFieldEntry
from .settings import (
    CORRESPONDENCE_AUTHOR_COMPLETION_FUNCTION,
    CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS,
    CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION,
)


class ProfileCompletionStatus(StrEnum):
    """
    Enumeration of profile completion statuses.

    Profile completion status is only meant as way for the backend to provide the frontend more nuanced
    profile validation rather than: "user cannot submit".
    This class defines different statuses to indicate the state of a
    profile's completion or eligibility. It helps in categorizing accounts
    based on their completeness or specific requirements like ORCID linkage.

    :ivar INCOMPLETE_ACCOUNT: Indicates that the account is incomplete (but user can edit their own profile).
    :type INCOMPLETE_ACCOUNT: str
    :ivar INELIGIBLE_ACCOUNT: Indicates that the account is ineligible.
    :type INELIGIBLE_ACCOUNT: str
    :ivar ORCID_MISSING_ACCOUNT: Indicates the account lacks a required ORCID.
        It may be not blocking depending on the journal.
    :type ORCID_MISSING_ACCOUNT: str
    """

    INCOMPLETE_ACCOUNT = "incomplete_account"
    INELIGIBLE_ACCOUNT = "ineligible_account"
    ORCID_MISSING_ACCOUNT = "orcid_missing_account"


def default_correspondence_author_completion(
    disabled_users: Iterable, user: Account, is_owner: bool
) -> ProfileCompletionStatus | None:
    """
    Verify user profile completions status.

    Completion status per-se is just a string identifier that can be used by the view's template to indicate
    required/desirable actions to the operator.

    The "hard-blocking" logic is fed in this function via `disabled_users` parameter, which allows this function
    to check if the user is hard-blocked from submission; this function can add additional checks to provide more
    information about why the user is not allowed to submit and how to resolve it (in the default implementation,
    the owner can be redirected to their profile page to update their profile).

    :param disabled_users: Iterable of users who are disabled or restricted
    :type disabled_users: Iterable
    :param user: The user account to validate
    :type user: Account
    :param is_owner: Whether the user is the owner (ie: submitter) of the article
    :type is_owner: bool
    :return: True if the user is valid as a correspondence author, False otherwise
    :rtype: bool
    """
    if user.pk in disabled_users:
        if is_owner:
            return ProfileCompletionStatus.INCOMPLETE_ACCOUNT
        return ProfileCompletionStatus.INELIGIBLE_ACCOUNT
    if not user.orcid:
        return ProfileCompletionStatus.ORCID_MISSING_ACCOUNT
    return None


def _resolve_path(user: Account, path: str):
    """
    Resolve a dotted attribute path on the user, calling the final value if it is callable.

    Paths must end on a field, a property or a no-argument method (not on a related manager).
    """
    value = user
    for attribute in path.split("."):
        value = getattr(value, attribute)
    return value() if callable(value) else value


def is_required_field_entry_satisfied(user: Account, entry: RequiredFieldEntry) -> bool:
    """
    Tell whether the user satisfies one entry of the required-fields dict.

    Without `allowed`, any of the entry's paths having a truthy value is enough; with `allowed`, any path value
    being in `allowed` is enough (no truthiness test).

    The paths are read from the account data whatever the profile pages show: a value in a field that the journal
    does not show (left from an import or from another journal) still satisfies the entry, and the author cannot
    see or edit it. The installing project must keep the paths of each entry limited to the fields its journals
    show; wjs-profile-project enforces this for its own rules with a startup system check.

    :param user: The user account to check
    :type user: Account
    :param entry: An entry of `CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS`
    :type entry: RequiredFieldEntry
    :return: True if the entry is satisfied
    :rtype: bool
    """
    values = (_resolve_path(user, path) for path in entry["paths"])
    allowed = entry.get("allowed")
    if allowed is None:
        return any(values)
    return any(value in allowed for value in values)


def get_required_field_entries(journal: Journal) -> list[RequiredFieldEntry]:
    """
    Return the required-fields entries of the journal (the `None` entry for journals without their own).

    :param journal: The journal whose rules apply
    :type journal: Journal
    :return: Entries with `label`, `paths` and optionally `allowed` (and any extra key set by the installing project)
    :rtype: list[RequiredFieldEntry]
    """
    return CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS.get(journal.code, CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS[None])


def missing_required_fields(user: Account, journal: Journal) -> list[str]:
    """
    Return the labels of the profile fields that the user still has to fill in to be a correspondence author.

    The rules are the journal's entry of `CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS` (the `None` entry for journals
    without their own). This is the single source of truth of the default validation: the user is valid if
    the list is empty. Labels are human-readable (translatable), suitable to be shown to the user.

    :param user: The user account to check
    :type user: Account
    :param journal: The journal whose rules apply
    :type journal: Journal
    :return: Labels of the missing fields, in the order of the rules; empty if the account is valid.
    :rtype: list[str]
    """
    return [
        entry["label"]
        for entry in get_required_field_entries(journal)
        if not is_required_field_entry_satisfied(user, entry)
    ]


def default_correspondence_author_validation(user: Account, journal: Journal) -> bool:
    """
    Validate whether a user meets the journal's required-fields rules to be a correspondence author.

    This is the default of the `CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION` injection point: a journal that needs
    different logic points that setting to its own function with the same signature.

    :param user: The user account to validate
    :type user: Account
    :param journal: The journal whose rules apply
    :type journal: Journal
    :return: True if the user is valid as a correspondence author, False otherwise
    :rtype: bool
    """
    return not missing_required_fields(user, journal)


def is_whitelisted_correspondence_author(journal: Journal, user: Account) -> bool:
    """Return True if the user is in the (currently valid) per-journal whitelist."""
    today = timezone.localtime(timezone.now()).date()
    user_qs = WhitelistedCorrespondenceAuthors.objects.filter(user=user, journal=journal)
    user_qs = user_qs.filter(
        Q(Q(validity_start_date__lte=today) | Q(validity_start_date__isnull=True))
        & Q(Q(validity_stop_date__gte=today) | Q(validity_stop_date__isnull=True))
    )
    return user_qs.exists()


def is_user_eligible_for_correspondence_author(journal: Journal, user: Account) -> bool:
    """
    Determine if a user is eligible to be a correspondence author for a journal.

    This function retrieves a validation control function based on the journal's code
    and applies it to check the eligibility of the given user.

    If user is added to per-journal whitelist, they are eligible to be selected as correspondence authors.

    :param journal: The journal for which correspondence author eligibility is checked
    :type journal: Journal
    :param user: The account of the user whose eligibility is being verified
    :type user: Account
    :return: True if the user is eligible, False otherwise
    :rtype: bool
    :raises KeyError: If the journal code is not found in the validation function mapping
    :raises ImportError: If the control function cannot be imported
    :raises TypeError: If the validation function is not callable
    """
    if is_whitelisted_correspondence_author(journal, user):
        return True

    control_function_name = CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION.get(
        journal.code, CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION[None]
    )
    control_function = import_string(control_function_name)
    return control_function(user, journal)


def verify_profile_completion(
    journal: Journal, disabled_users: Iterable, user: Account, is_owner: bool
) -> ProfileCompletionStatus | None:
    """
    Verify the completion status of a user's profile for a specific journal.

    This function retrieves a validation control function based on the journal's code
    and applies it to check the eligibility of the given user.

    :param journal: The journal for which profile completion needs to be verified
    :type journal: Journal
    :param disabled_users: Iterable of users who are disabled or restricted
    :type disabled_users: Iterable
    :param user: The account of the user whose profile is being verified
    :type user: Account
    :param is_owner: Whether the user is the owner (ie: submitter) of the article
    :type is_owner: bool
    :return: The result of the control function for verifying profile completion
    :rtype: bool
    :raises ImportError: If the control function cannot be imported
    :raises Exception: If the control function raises any other error during execution
    """
    control_function_name = CORRESPONDENCE_AUTHOR_COMPLETION_FUNCTION.get(
        journal.code, CORRESPONDENCE_AUTHOR_COMPLETION_FUNCTION[None]
    )
    control_function = import_string(control_function_name)
    return control_function(disabled_users, user, is_owner)


def get_correspondence_author_missing_fields(journal: Journal, user: Account) -> list[str]:
    """
    Return the profile fields that the user still has to fill in to be eligible as correspondence author.

    The journal's rules are read from `CORRESPONDENCE_AUTHOR_REQUIRED_FIELDS`. Whitelisted users are eligible, so
    nothing is missing for them.

    :param journal: The journal for which correspondence author eligibility is checked
    :type journal: Journal
    :param user: The account of the user whose profile is being checked
    :type user: Account
    :return: Labels of the missing fields; empty if the user is eligible.
    :rtype: list[str]
    """
    if is_whitelisted_correspondence_author(journal, user):
        return []
    return missing_required_fields(user, journal)
