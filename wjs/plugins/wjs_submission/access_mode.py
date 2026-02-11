from typing import NamedTuple

from core.models import Account, Country
from django.utils.module_loading import import_string
from submission.models import Article, Licence

from .models import AccessMode, AccessModeJournal, RevisionStorage
from .settings import ACCESS_MODE_CONTROL_FUNCTION, ACCESS_MODE_COUNTRIES, OA_CERN_CODE, OA_CODE


class AccessModeConfiguration(NamedTuple):
    """
    Represents a configuration for access mode.

    Defines the configuration for access modes, licenses, copyright text, and default status.
    This class is a named tuple and is useful for organizing access-related configuration
    details in a structured manner.

    :param access_mode: The access mode configuration, which can be an `AccessMode` instance
        or None.
    :type access_mode: AccessMode | None
    :param license: The license configuration, which can be a `Licence` instance or None.
    :type license: Licence | None
    :param copyright_text: The copyright text associated with the access mode.
    :type copyright_text: str
    :param user_can_select_access_mode: A flag indicating whether this configuration can be selected by the user or
     is mandatory.
    :type user_can_select_access_mode: bool
    """

    access_mode: AccessMode | None
    license: Licence | None
    copyright_text: str
    user_can_select_access_mode: bool


def get_access_mode_configuration(user: Account, article: Article) -> AccessModeConfiguration | None:
    """
    Determine and retrieve the access mode configuration for a given user and article.

    Load control function name from settings based on current journal code.

    :param user: User whose access configuration needs to be determined.
    :type user: Account
    :param article: Article for which the access configuration is being evaluated.
    :type article: Article
    :return: The access mode configuration based on the user's and article's association.
    :rtype: AccessModeConfiguration
    :raises KeyError: If the journal code from the article is not present in the
        ACCESS_MODE_CONTROL_FUNCTION dictionary.
    :raises ModuleNotFoundError: If the module specified in the control function name cannot
        be imported.
    :raises AttributeError: If the control function extracted cannot be found or is invalid.
    """
    control_function_name = ACCESS_MODE_CONTROL_FUNCTION.get(article.journal.code, ACCESS_MODE_CONTROL_FUNCTION[None])
    control_function = import_string(control_function_name)
    return control_function(user, article)


def noop(user: Account, article: Article) -> AccessModeConfiguration | None:
    """
    Provide default AccessModeConfiguration logic for journals without access mode control function.

    If the journal has exactly one access mode, configuration returns it as non selectable to force it.
    If the journal has no access mode or multiple access modes, configuration allows user to select it.

    :param user: An instance of the Account class representing the user whose
        access configuration is being processed.
    :param article: An instance of the Article class representing the article for
        which the access configuration is being requested.
    :return: An instance of the AccessModeConfiguration class containing details about
        the access mode, license, copyright text, and default status.
    :raises: No exceptions are raised.
    """
    try:
        journal_parameters = AccessModeJournal.objects.get(journal=article.journal)
        return AccessModeConfiguration(
            access_mode=journal_parameters.access_mode,
            license=journal_parameters.licence,
            copyright_text=journal_parameters.copyright,
            user_can_select_access_mode=False,
        )
    except AccessModeJournal.MultipleObjectsReturned:
        return AccessModeConfiguration(
            access_mode=None,
            license=None,
            copyright_text="",
            user_can_select_access_mode=True,
        )
    except AccessModeJournal.DoesNotExist:
        return None


def get_affiliation_country(article: Article) -> Country:
    """
    Retrieve the country of affiliation for a given article.

    Check the article's revision storage for the country of affiliation. If the
    country is found, retrieve the corresponding Country object. If the country
    is not found in the revision storage or the related Country object does not
    exist, return the country specified in the submission data of the article.

    :param article: The article instance containing information about the affiliation.
    :type article: Article
    :return: The Country instance representing the country of affiliation.
    :rtype: Country
    :raises Country.DoesNotExist: If the Country object corresponding to the
        affiliation country in the revision storage does not exist.
    :raises RevisionStorage.DoesNotExist: If the RevisionStorage related to the
        article does not exist.
    """
    try:
        country = article.revisionstorage.data.get("affiliation_country")
        if country:
            return Country.objects.get(pk=country)
    except (Country.DoesNotExist, RevisionStorage.DoesNotExist):
        pass
    return article.submission_data.affiliation_country


def get_oa_transformative_agreement(user: Account, article: Article) -> AccessModeConfiguration:
    """
    Get the open access transformative agreement configuration for a given user and article.

    Checks the affiliation country of the article against the list of countries eligible for
    the specified access mode. If the article's journal is eligible, it returns the
    configuration with appropriate settings; otherwise, it defaults to a configuration
    indicating no access.

    :param user: The user whose access permissions are being determined.
    :type user: Account
    :param article: The article for which the access configuration is being fetched.
    :type article: Article
    :return: The access mode configuration containing licensing and copyright information.
    :rtype: AccessModeConfiguration
    :raises AccessMode.DoesNotExist: If no access mode object with the specified code exists.
    :raises KeyError: If the journal code is not found in the ACCESS_MODE_COUNTRIES dictionary.
    """
    oa = AccessMode.objects.get(code=OA_CODE)
    countries = ACCESS_MODE_COUNTRIES.get(article.journal.code, ACCESS_MODE_COUNTRIES[None])
    affiliation_country = get_affiliation_country(article)
    if affiliation_country.code in countries:
        journal_parameters = oa.parameters.get(journal=article.journal)
        return AccessModeConfiguration(
            access_mode=oa,
            license=journal_parameters.licence,
            copyright_text=journal_parameters.copyright,
            user_can_select_access_mode=False,
        )
    return AccessModeConfiguration(
        access_mode=None,
        license=None,
        copyright_text="",
        user_can_select_access_mode=True,
    )


def get_oa_cern(user: Account, article: Article) -> AccessModeConfiguration:
    """
    Get the open access CERN agreement configuration for a given user and article.

    Checks the authors affiliations to match CERN affiliation, it defaults to a configuration
    indicating no access.

    :param user: The user whose access permissions are being determined.
    :type user: Account
    :param article: The article for which the access configuration is being fetched.
    :type article: Article
    :return: The access mode configuration containing licensing and copyright information.
    :rtype: AccessModeConfiguration
    :raises AccessMode.DoesNotExist: If no access mode object with the specified code exists.
    :raises KeyError: If the journal code is not found in the ACCESS_MODE_COUNTRIES dictionary.
    """
    oa = AccessMode.objects.get(code=OA_CERN_CODE)
    countries = ACCESS_MODE_COUNTRIES.get(article.journal.code, ACCESS_MODE_COUNTRIES[None])
    affiliation_country = get_affiliation_country(article)
    if affiliation_country.code in countries:
        journal_parameters = oa.parameters.get(journal=article.journal)
        return AccessModeConfiguration(
            access_mode=oa,
            license=journal_parameters.licence,
            copyright_text=journal_parameters.copyright,
            user_can_select_access_mode=False,
        )
    return AccessModeConfiguration(
        access_mode=None,
        license=None,
        copyright_text="",
        user_can_select_access_mode=True,
    )


def get_jquant_access_mode(user: Account, article: Article) -> AccessModeConfiguration:
    """
    Determine the access mode configuration for a user's access to a specific article.

    This function evaluates whether the user has an open-access transformative
    agreement (OAT) for the given article. If such an agreement exists and has
    an associated access mode, it returns the OAT configuration. Otherwise, it
    defaults to evaluating access via CERN's open access mechanism.

    :param user: The account object representing the user.
    :type user: Account
    :param article: The article object for which access mode is determined.
    :type article: Article
    :return: The configuration specifying the access mode for the user and article.
    :rtype: AccessModeConfiguration
    :raises SomeSpecificException: Raised if an error occurs during OA agreement retrieval.
    """
    oat = get_oa_transformative_agreement(user, article)
    if oat.access_mode:
        return oat
    return get_oa_cern(user, article)
