from django.conf import settings
from django.utils.translation import gettext_lazy as _

DEFAULT_KEYWORD_VALIDATORS = {
    None: ("plugins.wjs_submission.keywords.always_pass",),
    "JCOM": ("plugins.wjs_submission.keywords.always_pass",),
    "JCOMAL": ("plugins.wjs_submission.keywords.always_pass",),
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


KEYWORD_VALIDATORS = getattr(settings, "SUBMISSION_KEYWORD_VALIDATORS", DEFAULT_KEYWORD_VALIDATORS)
KEYWORD_FILTERS = getattr(settings, "SUBMISSION_KEYWORD_VALIDATORS", DEFAULT_KEYWORD_FILTERS)
ARTICLE_LANGUAGES = getattr(settings, "SUBMISSION_ARTICLE_LANGUAGES", DEFAULT_ARTICLE_LANGUAGES)

SIMULATE_YAKUNIN = getattr(settings, "SUBMISSION_SIMULATE_YAKUNIN", False)
