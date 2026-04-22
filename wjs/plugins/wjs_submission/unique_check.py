from django.db.models import Q, QuerySet
from django.utils.module_loading import import_string
from identifiers.models import Identifier
from journal.models import Journal
from submission.models import STAGE_REJECTED, STAGE_UNSUBMITTED, Article

from .plugin_settings import UNIQUENESS_CHECK


def get_article_matching_signature(response_content: dict, journal: Journal = None) -> QuerySet:
    """
    Retrieve article candidates based on the provided response content.

    Matches articles using either the 'arxiv_id', title, abstract, or identifiers already associated with articles.

    :param response_content: A dictionary containing 'arxiv_id', 'title',
        and 'abstract' keys to filter candidate articles.
    :type response_content: dict
    :param journal: The Journal instance to filter candidates by.
    :type journal: Journal
    :return: A queryset of Article objects that match the given criteria.
    :rtype: QuerySet
    :raises KeyError: If required keys ('arxiv_id', 'title', 'abstract') are missing in
        the response_content.
    """
    articles_by_identifier = Identifier.objects.filter(
        identifier=response_content["arxiv_id"],
        id_type="arxiv",
        article__isnull=False,
    ).values_list("article", flat=True)
    filtered_articles = Article.objects.filter(
        Q(
            title__iexact=response_content["title"],
            abstract__iexact=response_content["abstract"],
        )
        | Q(pk__in=articles_by_identifier),
    )
    if journal:
        filtered_articles = filtered_articles.filter(journal=journal)
    return filtered_articles


def check_article_uniqueness_by_submission_status(
    response_content: dict, journal: Journal, arxiv_article_id: int
) -> bool:
    """
    Check that Article is unique by submission status and Journal.

    Checks:
    - An Article with the same ArXiv ID already exists and state not in (withdrawn, unsubmitted)
    - An Article with the same title and abstract already exists and state not in (withdrawn, unsubmitted)

    :param response_content: A dictionary containing 'arxiv_id', 'title',
        and 'abstract' keys to filter candidate articles.
    :type response_content: dict
    :param journal: The Journal instance to filter candidates by.
    :type journal: Journal
    :param arxiv_article_id: The ArXiv article id to filter candidates by.
    :type arxiv_article_id: int
    :return: A boolean
    :rtype: bool
    """
    filtered_articles = get_article_matching_signature(response_content=response_content, journal=journal)

    filtered_articles = filtered_articles.exclude(
        # Unsubmitted / rejected articles can be re-submitted under new ID
        Q(stage__in={STAGE_UNSUBMITTED, STAGE_REJECTED})
        |
        # If current step is 0, it's an article which just have been created via ArxivMicroservice
        Q(current_step=0)
        |
        # current article being submitted (this is an edit of an existing incomplete submission)
        Q(pk=arxiv_article_id)
    )
    return not filtered_articles.exists()


def check_article_unique(response_content: dict, journal: Journal, arxiv_article_id: int) -> bool:
    """
    Get correct function to check that Article is unique.

    :param response_content: A dictionary containing 'arxiv_id', 'title',
    and 'abstract' keys to filter candidate articles.
    :type response_content: dict
    :param journal: The Journal instance to filter candidates by.
    :type journal: Journal
    :param arxiv_article_id: The ArXiv article id to filter candidates by.
    :type arxiv_article_id: int
    :return: A boolean
    :rtype: bool
    """
    check_article_unique_function_name = UNIQUENESS_CHECK.get(journal.code, UNIQUENESS_CHECK[None])
    check_article_unique_function = import_string(check_article_unique_function_name)
    return check_article_unique_function(
        response_content=response_content, journal=journal, arxiv_article_id=arxiv_article_id
    )
