from django.conf import settings

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

KEYWORD_VALIDATORS = getattr(settings, "KEYWORD_VALIDATORS", DEFAULT_KEYWORD_VALIDATORS)
KEYWORD_FILTERS = getattr(settings, "KEYWORD_VALIDATORS", DEFAULT_KEYWORD_FILTERS)
