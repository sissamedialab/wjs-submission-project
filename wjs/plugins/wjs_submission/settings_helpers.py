from journal.models import Journal

from . import settings


def get_article_language_choices(journal: Journal) -> list[tuple[str, str]]:
    """
    Get the language choices for a journal.

    See https://gitlab.sissamedialab.it/wjs/wjs-profile-project/-/merge_requests/144

    :param journal: the journal
    :type journal: Journal

    :return: the language choices
    :rtype: List[Tuple[str, str]]
    """
    return settings.ARTICLE_LANGUAGES.get(journal.code, settings.ARTICLE_LANGUAGES.get(None))
