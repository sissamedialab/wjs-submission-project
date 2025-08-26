from django.db.models import Q, QuerySet
from journal.models import Journal
from submission.models import KeywordGroup


def get_keywords_by_journal(journal: Journal) -> QuerySet:
    """
    Fetch top-level keyword groups associated with the keywords of the provided journal.

    Keyword groups are filtered by matching keywords or by their association with matching groups.

    :param journal: The journal object whose keywords will be used to retrieve associated top-level keyword groups.
    :type journal: Journal

    :return: A queryset of distinct top-level keyword groups linked to the journal's keywords.
    :rtype: QuerySet

    :raises: Any exception that occurs during queryset execution or database access.
    """
    # TODO: This is a limited implementation of the keyword filtering logic.
    #  It should be extended to support arbitrary keyword groups depth.
    groups_all = KeywordGroup.objects.filter(keywords__in=journal.keywords.all())
    filter_by_keyword = Q(keywordgroup__in=groups_all) | Q(keywords__in=journal.keywords.all())
    return KeywordGroup.objects.filter(parent_group__isnull=True).filter(filter_by_keyword).distinct()
