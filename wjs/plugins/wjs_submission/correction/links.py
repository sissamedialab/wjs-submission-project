from submission.models import Article

from .logic import CORRECTION_RELATIONSHIPS


def correction_parent(article: Article) -> Article | None:
    """
    Identify and return the first article that is linked to the given article based on specific relationship rules.

    Search for articles linked to the provided article, excluding those connected through subordinate relationships.
    Order the results by their position in the link hierarchy, ensuring the earliest suitable article is returned.
    If no matches are found, return None.

    :param article: The target article to find linked relationships for.
    :type article: Article
    :return: The first article that matches the criteria or None if no match is found.
    :rtype: Article | None
    """
    return (
        Article.objects.filter(
            linked_from__to_article=article,
        )
        .exclude(linked_to__relationship__in=CORRECTION_RELATIONSHIPS)
        .order_by("linked_from__order", "linked_from__id")
        .first()
    )
