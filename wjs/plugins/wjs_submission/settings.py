from django.conf import settings
from django.utils.translation import gettext_lazy as _

DEFAULT_KEYWORDS_INTERVAL_PER_JOURNAL = {
    None: (1, 3),
    "JQuant": (2, 4),
    "JHEP": (1, 4),
}

DEFAULT_KEYWORD_VALIDATORS = {
    None: ("plugins.wjs_submission.keywords.always_pass",),
    "JCOM": ("plugins.wjs_submission.keywords.basic_keyword_selection_rule",),
    "JCOMAL": ("plugins.wjs_submission.keywords.basic_keyword_selection_rule",),
    "JQuant": ("plugins.wjs_submission.keywords.jquant_keyword_selection_rule",),
    "JHEP": ("plugins.wjs_submission.keywords.jhep_keyword_selection_rule",),
}

DEFAULT_KEYWORD_FILTERS = {
    None: "plugins.wjs_submission.keywords.get_keywords_by_journal",
    "JCOM": "plugins.wjs_submission.keywords.get_keywords_by_journal",
    "JCOMAL": "plugins.wjs_submission.keywords.get_keywords_by_journal",
    "JQuant": "plugins.wjs_submission.keywords.get_keywords_by_journal",
    "JHEP": "plugins.wjs_submission.keywords.get_keywords_by_journal_and_arxiv_category",
}

DEFAULT_ARTICLE_LANGUAGES = {
    None: [("eng", _("English"))],
}

DEFAULT_ACCESS_MODE_CONTROL_FUNCTION = {
    None: "plugins.wjs_submission.access_mode.noop",
    "JINST": "plugins.wjs_submission.access_mode.get_cern_oata_fallback_access_mode",
    "JQuant": "plugins.wjs_submission.access_mode.get_cern_journals_access_mode",
    "JHEP": "plugins.wjs_submission.access_mode.get_cern_journals_access_mode",
}


DEFAULT_CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION = {
    "JCAP": "plugins.wjs_submission.account_validation.jcap_correspondence_author_validation",
    "JCOM": "plugins.wjs_submission.account_validation.jcom_correspondence_author_validation",
    "JCOMAL": "plugins.wjs_submission.account_validation.jcom_correspondence_author_validation",
    None: "plugins.wjs_submission.account_validation.default_correspondence_author_validation",
}

DEFAULT_CORRESPONDENCE_AUTHOR_COMPLETION_FUNCTION = {
    None: "plugins.wjs_submission.account_validation.default_correspondence_author_completion",
}

COUNTRIES_TA = [
    "AU",  # Australia
    "AT",  # Austria
    "BW",  # Botswana
    "BG",  # Bulgaria
    "CA",  # Canada
    "CL",  # Chile
    "CN",  # China
    "CO",  # Colombia
    "HR",  # Croatia
    "CZ",  # Czechia
    "DK",  # Denmark
    "FI",  # Finland
    "FR",  # France
    "DE",  # Germany
    "GR",  # Greece
    "HK",  # Hong Kong, SAR
    "HU",  # Hungary
    "IN",  # India
    "IE",  # Ireland
    "IL",  # Israel
    "IT",  # Italy
    "JP",  # Japan
    "LB",  # Lebanon
    "LT",  # Lithuania
    "MO",  # Macau
    "MY",  # Malaysia
    "MX",  # Mexico
    "NZ",  # New Zealand
    "NO",  # Norway
    "PE",  # Peru
    "PL",  # Poland
    "PT",  # Portugal
    "RO",  # Romania
    "NL",  # The Netherlands
    "SA",  # Saudi Arabia
    "SK",  # Slovakia
    "SI",  # Slovenia
    "ZA",  # South Africa
    "KR",  # South Korea
    "ES",  # Spain
    "SE",  # Sweden
    "CH",  # Switzerland
    "TW",  # Taiwan
    "TN",  # Tunisia
    "TR",  # Turkey
    "GB",  # United Kingdom
    "US",  # United States
]

DEFAULT_ACCESS_MODE_COUNTRIES = {
    None: [],
    "JSTAT": COUNTRIES_TA,
    "JCAP": COUNTRIES_TA,
    "JINST": COUNTRIES_TA,
}

CERN_AFFILIATIONS = ["alice", "lhcb", "lhcf", "atlas", "cms"]

DEFAULT_SUBMISSION_FILE_TYPES = {
    None: ("text/x-tex", "application/zip", "application/gzip"),
    "JCOM": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.oasis.opendocument.text",
    ),
    "JCOMAL": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.oasis.opendocument.text",
    ),
}


KEYWORDS_INTERVAL_PER_JOURNAL = getattr(
    settings, "SUBMISSION_KEYWORDS_INTERVAL_PER_JOURNAL", DEFAULT_KEYWORDS_INTERVAL_PER_JOURNAL
)
KEYWORD_VALIDATORS = getattr(settings, "SUBMISSION_KEYWORD_VALIDATORS", DEFAULT_KEYWORD_VALIDATORS)
KEYWORD_FILTERS = getattr(settings, "SUBMISSION_KEYWORD_VALIDATORS", DEFAULT_KEYWORD_FILTERS)
ARTICLE_LANGUAGES = getattr(settings, "SUBMISSION_ARTICLE_LANGUAGES", DEFAULT_ARTICLE_LANGUAGES)

SIMULATE_YAKUNIN = getattr(settings, "SUBMISSION_SIMULATE_YAKUNIN", False)

YAKUNIN_SHOW_DETAILED_LOG = getattr(settings, "SUBMISSION_YAKUNIN_SHOW_DETAILED_LOG", False)

ACCESS_MODE_COUNTRIES = getattr(settings, "SUBMISSION_ACCESS_MODE_COUNTRIES", DEFAULT_ACCESS_MODE_COUNTRIES)
ACCESS_MODE_CONTROL_FUNCTION = getattr(
    settings,
    "SUBMISSION_ACCESS_MODE_CONTROL_FUNCTION",
    DEFAULT_ACCESS_MODE_CONTROL_FUNCTION,
)
OA_CODE_TA = getattr(settings, "SUBMISSION_OA_CODE_TA", "oa-transformative-agreement")
OA_CERN_CODE = getattr(settings, "SUBMISSION_OA_CERN_CODE", "oa-cern")
OA_CODE = getattr(settings, "SUBMISSION_OA_CODE", "open-access")

CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION = getattr(
    settings, "SUBMISSION_CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION", DEFAULT_CORRESPONDENCE_AUTHOR_VALIDATION_FUNCTION
)

CORRESPONDENCE_AUTHOR_COMPLETION_FUNCTION = getattr(
    settings, "SUBMISSION_CORRESPONDENCE_AUTHOR_COMPLETION_FUNCTION", DEFAULT_CORRESPONDENCE_AUTHOR_COMPLETION_FUNCTION
)

SUBMISSION_FILE_TYPES = getattr(settings, "SUBMISSION_FILE_TYPES", DEFAULT_SUBMISSION_FILE_TYPES)

ARXIV_BASE_DOI = getattr(settings, "SUBMISSION_ARXIV_BASE_DOI", "https://doi.org/10.48550")

RESET_ARTICLE_CURRENT_STEP = getattr(settings, "REVISION_RESET_ARTICLE_CURRENT_STEP", False)

DEFAULT_USE_OF_AI_FIELD_LABEL = getattr(
    settings,
    "SUBMISSION_DEFAULT_USE_OF_AI_FIELD_LABEL",
    "Author(s) take full responsibility for any use of Artificial Intelligence made in preparing this paper",
)
USE_OF_AI_FIELD_LABEL = getattr(settings, "SUBMISSION_USE_OF_AI_FIELD_LABEL", DEFAULT_USE_OF_AI_FIELD_LABEL)
