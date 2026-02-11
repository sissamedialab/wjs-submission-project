from django.conf import settings
from django.utils.translation import gettext_lazy as _

DEFAULT_KEYWORD_VALIDATORS = {
    None: ("plugins.wjs_submission.keywords.always_pass",),
    "JCOM": ("plugins.wjs_submission.keywords.basic_keyword_selection_rule",),
    "JCOMAL": ("plugins.wjs_submission.keywords.basic_keyword_selection_rule",),
    "JQUANT": ("plugins.wjs_submission.keywords.jquant_keyword_selection_rule",),
    "JHEP": ("plugins.wjs_submission.keywords.jhep_keyword_selection_rule",),
}

DEFAULT_KEYWORD_FILTERS = {
    None: "plugins.wjs_submission.keywords.get_keywords_by_journal",
    "JCOM": "plugins.wjs_submission.keywords.get_keywords_by_journal",
    "JCOMAL": "plugins.wjs_submission.keywords.get_keywords_by_journal",
    "JQUANT": "plugins.wjs_submission.keywords.get_keywords_by_journal",
    "JHEP": "plugins.wjs_submission.keywords.get_keywords_by_journal_and_arxiv_category",
}

DEFAULT_ARTICLE_LANGUAGES = {
    None: [("eng", _("English"))],
}

DEFAULT_ACCESS_MODE_CONTROL_FUNCTION = {
    None: "plugins.wjs_submission.access_mode.noop",
    "JQUANT": "plugins.wjs_submission.access_mode.get_oa_cern",
}

DEFAULT_ACCESS_MODE_COUNTRIES = {
    None: [],
    "JQUANT": ["FR", "IT", "GB"],
}


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


KEYWORD_VALIDATORS = getattr(settings, "SUBMISSION_KEYWORD_VALIDATORS", DEFAULT_KEYWORD_VALIDATORS)
KEYWORD_FILTERS = getattr(settings, "SUBMISSION_KEYWORD_VALIDATORS", DEFAULT_KEYWORD_FILTERS)
ARTICLE_LANGUAGES = getattr(settings, "SUBMISSION_ARTICLE_LANGUAGES", DEFAULT_ARTICLE_LANGUAGES)

SIMULATE_YAKUNIN = getattr(settings, "SUBMISSION_SIMULATE_YAKUNIN", True)

ACCESS_MODE_COUNTRIES = getattr(settings, "SUBMISSION_ACCESS_MODE_COUNTRIES", DEFAULT_ACCESS_MODE_COUNTRIES)
ACCESS_MODE_CONTROL_FUNCTION = getattr(
    settings,
    "SUBMISSION_ACCESS_MODE_CONTROL_FUNCTION",
    DEFAULT_ACCESS_MODE_CONTROL_FUNCTION,
)
OA_CODE = getattr(settings, "SUBMISSION_OA_CODE", "oa-transformative-agreement")
OA_CERN_CODE = getattr(settings, "SUBMISSION_OA_CERN_CODE", "oa-cern")

SUBMISSION_FILE_TYPES = getattr(settings, "SUBMISSION_FILE_TYPES", DEFAULT_SUBMISSION_FILE_TYPES)

ARXIV_BASE_DOI_ = getattr(settings, "SUBMISSION_ARXIV_BASE_DOI_", "https://doi.org/10.48550/")
