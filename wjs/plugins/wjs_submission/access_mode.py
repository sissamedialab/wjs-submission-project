from typing import NamedTuple

from core.models import Account, ControlledAffiliation, Country
from django.db.models import QuerySet
from django.utils.module_loading import import_string
from journal.models import Journal
from submission.models import Article, Licence

from .models import AccessMode, AccessModeJournal, RevisionStorage
from .settings import (
    ACCESS_MODE_CONTROL_FUNCTION,
    ACCESS_MODE_COUNTRIES,
    CERN_AFFILIATIONS,
    CORRECTION_ACCESS_MODE_CODE,
    OA_CERN_CODE,
    OA_CODE,
    OA_CODE_TA,
    OA_MESSAGE_CODES,
)
from .workflow import is_correction, is_revision, is_revision_full, is_revision_metadata


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


def get_configuration(access_mode: AccessMode | None, journal: Journal, user_selectable: bool | None = None):
    """
    Retrieve the configuration for a given journal based on the provided access mode.

    :param access_mode: The access mode object or None
    :type access_mode: AccessMode | None
    :param journal: The journal for which the configuration is being retrieved
    :type journal: Journal
    :return: Configuration for the journal, including license, copyright text, and
             user access mode selection
    :rtype: AccessModeConfiguration
    :raises AttributeError: If 'parameters', 'licence', or 'copyright' is accessed from
                             an invalid or improperly defined access mode
    """
    journal_parameters = None
    if access_mode:
        journal_parameters = access_mode.parameters.get(journal=journal)
    elif user_selectable is None:
        user_selectable = AccessModeJournal.objects.filter(journal=journal).count() > 1
    return AccessModeConfiguration(
        access_mode=access_mode,
        license=journal_parameters.licence if access_mode else None,
        copyright_text=journal_parameters.copyright if access_mode else "",
        user_can_select_access_mode=access_mode.user_selectable
        if access_mode and user_selectable is None
        else user_selectable,
    )


def get_access_mode_configuration(user: Account, article: Article) -> AccessModeConfiguration | None:
    """
    Determine and retrieve the access mode configuration for a given user and article.

    The rules, in this order:

    1. corrections: access mode, licence and rights are those set up when the correction was created (the access mode
       comes from ``CORRECTION_ACCESS_MODE_CODE``), not selectable;
    2. revisions where neither the corresponding author nor the affiliation changed: access mode, licence and rights
       of the article are kept, not selectable;
    3. anything else: the result of the control function of the journal (loaded from settings by the journal code).

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
    if is_correction(article) or is_revision_access_settings_unchanged(article):
        return get_article_access_mode_configuration(article)
    control_function_name = ACCESS_MODE_CONTROL_FUNCTION.get(article.journal.code, ACCESS_MODE_CONTROL_FUNCTION[None])
    control_function = import_string(control_function_name)
    return control_function(user, article)


def is_revision_access_settings_unchanged(article: Article) -> bool:
    """
    Tell if a revision keeps the corresponding author and the affiliation the article had before the revision.

    In this case the access mode, copyright and licence must not be recalculated: they are kept as they were set before
    the revision (including the changes made by the EO).

    :param article: The article, possibly being revised.
    :return: True if the article is being revised, has an access mode and neither the corresponding author nor the
        affiliation have been changed in the revision.
    """
    if not article.pk or not is_revision(article):
        return False
    try:
        data = article.revisionstorage.data
        submission_data = article.submission_data
    except (RevisionStorage.DoesNotExist, AttributeError):
        return False
    if not submission_data.access_mode_id:
        return False
    return str(data.get("correspondence_author")) == str(article.correspondence_author_id) and str(
        data.get("affiliation_pk")
    ) == str(submission_data.affiliation_id)


def get_article_access_mode_configuration(article: Article) -> AccessModeConfiguration:
    """
    Return the (fixed) access mode configuration built from the values currently set on the article.

    :param article: The article.
    :return: The configuration with the access mode, licence and copyright of the article, not selectable.
    """
    return AccessModeConfiguration(
        access_mode=article.submission_data.access_mode,
        license=article.license,
        copyright_text=article.rights or "",
        user_can_select_access_mode=False,
    )


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
        access_mode = AccessMode.objects.get(code=OA_CODE, parameters__journal=article.journal)
        return get_configuration(access_mode, article.journal, user_selectable=False)
    except AccessMode.MultipleObjectsReturned:
        return get_configuration(None, article.journal, user_selectable=True)
    except AccessMode.DoesNotExist:
        return None


def get_affiliation_country(article: Article) -> Country | None:
    """
    Retrieve the country of affiliation for a given article.

    While a revision is in progress the affiliation being edited is the one snapshotted in the
    article's revision storage, as the submission data is only updated on submission: check it
    first and fall back to the submission data one, which is also the affiliation used for
    articles which are not being revised.

    :param article: The article instance containing information about the affiliation.
    :type article: Article
    :return: The Country instance representing the country of affiliation. It might be None if affiliation is not
        complete
    :rtype: Country | None
    """
    try:
        if is_revision(article) and (affiliation_pk := article.revisionstorage.data.get("affiliation_pk")):
            affiliation = ControlledAffiliation.objects.get(pk=affiliation_pk)
        else:
            affiliation = article.submission_data.affiliation
        country = affiliation.organization.country
    except (
        ControlledAffiliation.DoesNotExist,
        RevisionStorage.DoesNotExist,
        AttributeError,
        ValueError,
        TypeError,
    ):
        # Even if affiliation exists, it might have null organization or country, which are not guaranteed by
        # janeway's models. In this case we can only consider this value null
        country = None
    return country


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
    oa = AccessMode.objects.get(code=OA_CODE_TA)
    countries = ACCESS_MODE_COUNTRIES.get(article.journal.code, ACCESS_MODE_COUNTRIES[None])
    affiliation_country = get_affiliation_country(article)
    if affiliation_country and affiliation_country.code in countries:
        return get_configuration(oa, article.journal)
    return get_configuration(None, article.journal)


def get_oa_cern(user: Account, article: Article) -> AccessModeConfiguration:
    """
    Get the open access CERN agreement configuration for a given user and article.

    Checks the article collaboration to match CERN collaborations, it defaults to a configuration
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
    collaborations = {collaboration.collaboration.name.lower() for collaboration in article.collaborations.all()}
    if collaborations.intersection(CERN_AFFILIATIONS):
        return get_configuration(oa, article.journal)
    return get_configuration(None, article.journal)


def get_cern_journals_access_mode(user: Account, article: Article) -> AccessModeConfiguration:
    """
    Determine the access mode configuration for a user's access to a specific article.

    This function evaluates whether the article is linked to any CERN collaboration and fallbacks
    to open-access (without user selection).

    :param user: The account object representing the user.
    :type user: Account
    :param article: The article object for which access mode is determined.
    :type article: Article
    :return: The configuration specifying the access mode for the user and article.
    :rtype: AccessModeConfiguration
    :raises SomeSpecificException: Raised if an error occurs during OA agreement retrieval.
    """
    oat = get_oa_cern(user, article)
    if oat.access_mode:
        return oat
    access_mode = AccessMode.objects.filter(code=OA_CODE, parameters__journal=article.journal).first()
    if not access_mode:
        raise RuntimeError("Missing OA agreement for CERN collaborations")
    return get_configuration(access_mode, article.journal, user_selectable=False)


def get_cern_oata_fallback_access_mode(user: Account, article: Article) -> AccessModeConfiguration:
    """
    Determine the access mode configuration for a user's access to a specific article.

    This function evaluates whether the article is linked to any CERN collaboration and fallbacks
    to open-access transformative agreement (OAT) if not.

    :param user: The account object representing the user.
    :type user: Account
    :param article: The article object for which access mode is determined.
    :type article: Article
    :return: The configuration specifying the access mode for the user and article.
    :rtype: AccessModeConfiguration
    :raises SomeSpecificException: Raised if an error occurs during OA agreement retrieval.
    """
    oat = get_oa_cern(user, article)
    if oat.access_mode:
        return oat
    return get_oa_transformative_agreement(user, article)


def get_access_modes_with_disclaimer(article: Article) -> QuerySet[AccessMode]:
    """
    Return list of access modes that require a disclaimer for the given article.

    :param article: The article object for which access modes are retrieved.
    :type article: Article
    :return: A querySet of access modes that require a disclaimer.
    :rtype: QuerySet[AccessMode]
    """
    codes = OA_MESSAGE_CODES.get(article.journal.code, OA_MESSAGE_CODES[None])
    return AccessMode.objects.filter(code__in=codes, parameters__journal=article.journal)


def get_correction_access_mode(journal: Journal) -> AccessMode:
    """
    Return the access mode used for corrections (errata/addenda) of the given journal.

    The access mode code is read from ``CORRECTION_ACCESS_MODE_CODE``, falling back to its default (``None`` key).

    :param journal: The journal of the article being corrected.
    :type journal: Journal
    :return: The access mode corrections of the journal are published with.
    :rtype: AccessMode
    :raises AccessMode.DoesNotExist: If the configured access mode does not exist.
    """
    code = CORRECTION_ACCESS_MODE_CODE.get(journal.code, CORRECTION_ACCESS_MODE_CODE[None])
    return AccessMode.objects.get(code=code)


def get_effective_access_settings(article: Article) -> tuple[AccessMode | None, Licence | None, str]:
    """
    Return the access mode, licence and rights that apply to the article, as shown in the review step.

    The values are those stored on the article. While a full or metadata revision is in progress the access mode is the
    one selected in step 7 and kept in the revision storage: if it differs from the stored one it is not applied to the
    article until the revision is submitted, so the presets of the new access mode are returned (the override flags are
    cleared when the revision is submitted, see ``PopulateRevisionStep7``).

    :param article: The article being reviewed.
    :return: Access mode, licence and rights (empty string if not set).
    """
    submission_data = article.submission_data
    access_mode = submission_data.access_mode
    licence, rights = article.license, article.rights or ""
    if is_revision_full(article) or is_revision_metadata(article):
        stored_id = article.revisionstorage.data.get("access_mode")
        if stored_id and stored_id != submission_data.access_mode_id:
            access_mode = AccessMode.objects.get(pk=stored_id)
            preset = AccessModeJournal.objects.get(access_mode=access_mode, journal=article.journal)
            licence, rights = preset.licence, preset.copyright
    return access_mode, licence, rights
