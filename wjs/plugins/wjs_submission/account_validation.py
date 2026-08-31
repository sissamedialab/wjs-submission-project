from collections.abc import Iterable
from enum import StrEnum

from core.models import Account
from django.db.models import Q
from django.utils import timezone
from django.utils.module_loading import import_string
from journal.models import Journal

from .models import WhitelistedCorrespondenceAuthors
from .settings import (
    CORRESPONDENCE_AUTHOR_COMPLETION_FUNCTION,
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


def default_correspondence_author_validation(user: Account) -> bool:
    """
    Validate whether a user meets the default criteria to be a correspondence author.

    :param user: The user account to validate
    :type user: Account
    :return: True if the user is valid as a correspondence author, False otherwise
    :rtype: bool
    """
    is_active = user.is_active
    personal_data = (user.last_name or user.first_name) and user.email
    professional_data = user.institution
    return is_active and personal_data and professional_data


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
    user_qs = WhitelistedCorrespondenceAuthors.objects.filter(user=user, journal=journal)
    user_qs = user_qs.filter(
        Q(Q(validity_start_date__lte=timezone.localtime(timezone.now()).date()) | Q(validity_start_date__isnull=True))
        & Q(Q(validity_stop_date__gte=timezone.localtime(timezone.now()).date()) | Q(validity_stop_date__isnull=True))
    )
    if user_qs.exists():
        return True

    control_function_name = CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION.get(
        journal.code, CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION[None]
    )
    control_function = import_string(control_function_name)
    return control_function(user)


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
