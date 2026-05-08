from django.db.models import Q, QuerySet
from journal.models import Journal
from submission.models import Keyword, KeywordGroup

from .settings import KEYWORDS_INTERVAL_PER_JOURNAL


def get_keyword_range_by_journal(journal: Journal) -> tuple[int, int]:
    """
    Retrieve the keyword range tuple for a given journal.

    This function uses the journal's code to look up the corresponding keyword
    range from a predefined mapping. If no match is found for the given journal,
    it defaults to using the keyword range for `None`.

    :param journal: The Journal instance for which the keyword range is sought.
    :type journal: Journal
    :return: A tuple containing the lower and upper bounds of the keyword range.
    :rtype: tuple[int, int]
    """
    return KEYWORDS_INTERVAL_PER_JOURNAL.get(journal.code, KEYWORDS_INTERVAL_PER_JOURNAL[None])


def get_keywords_by_journal(journal: Journal, arxiv_category: str | None = None) -> QuerySet:
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
    if journal.submissionconfiguration.hierarchical_keywords:
        groups_all = KeywordGroup.objects.filter(keywords__journal=journal)
        filter_by_keyword = Q(keywordgroup__in=groups_all) | Q(keywords__journal=journal)
        return (
            KeywordGroup.objects.filter(parent_group__isnull=True)
            .filter(filter_by_keyword)
            .distinct()
            .order_by("parent_group", "order")
        )
    return Keyword.objects.filter(journal=journal).distinct()


def get_keywords_by_journal_and_arxiv_category(journal, arxiv_category=None):
    """
    Fetch top-level keyword groups associated with the keywords of JHEP.

    Filtered according to arxiv_category rules. Only includes keywords that belong to a group.

    :param journal: Journal instance
    :param arxiv_category: Optional arXiv category
    :return: QuerySet of distinct top-level KeywordGroups
    """
    qs = Keyword.objects.filter(journal=journal, group__isnull=False).select_related("group")

    if arxiv_category == "hep-ex":
        qs = qs.filter(group__name="hep-ex")
    else:
        qs = qs.exclude(group__name="hep-ex")

    groups_all = KeywordGroup.objects.filter(keywords__in=qs)
    return (
        KeywordGroup.objects.filter(parent_group__isnull=True)
        .filter(Q(pk__in=groups_all) | Q(keywords__in=qs))
        .distinct()
    )


def always_pass(
    keyword_weights: dict,
    journal: Journal | None = None,
    arxiv_category: str | None = None,
) -> tuple[bool, str | None]:
    """
    Stub method to simulate keyword validation depending on journal (and, for JHEP, arxiv category).

    :return: True
    """
    return True, None


def basic_keyword_selection_rule(
    keyword_weights: dict,
    journal: Journal,
    arxiv_category: str | None = None,
) -> tuple[bool, str | None]:
    """
    Validate keyword selection for JCOM and JCOMAL submissions.

    Rules:
    - A submission must include a range of keywords defined in KEYWORDS_INTERVAL_PER_JOURNAL settin.

    :param keyword_weights: Dictionary of keyword_id -> weight.
    :param journal: Journal instance against which keywords are validated.
    :param arxiv_category: Optional arXiv category (unused here).
    :return: Tuple (is_valid, error_message). If valid, error_message is None.
    """
    keyword_range = get_keyword_range_by_journal(journal)
    count = len(keyword_weights)
    if not (keyword_range[0] <= count <= keyword_range[1]):
        return False, f"You must select between {keyword_range[0]} and {keyword_range[1]} keywords."
    return True, None


def jquant_keyword_selection_rule(
    keyword_weights: dict,
    journal: Journal,
    arxiv_category: str | None = None,
) -> tuple[bool, str | None]:
    """
    Validate keyword selection for JQuant submissions.

    Rules:
    - A submission must include a range of keywords defined in KEYWORDS_INTERVAL_PER_JOURNAL settin.
    - All keyword IDs must exist in the database and belong to the given journal.
    - All keywords must belong to a group (free keywords are not allowed).

    :param keyword_weights: Dictionary of keyword_id -> weight.
    :param journal: Journal instance against which keywords are validated.
    :param arxiv_category: Optional arXiv category (unused here).
    :return: Tuple (is_valid, error_message). If valid, error_message is None.
    """
    keyword_range = get_keyword_range_by_journal(journal)
    count = len(keyword_weights)
    if not (keyword_range[0] <= count <= keyword_range[1]):
        return False, f"You must select between {keyword_range[0]} and {keyword_range[1]} keywords."

    submitted_ids = set(keyword_weights.keys())

    keywords = list(journal.keywords.filter(id__in=submitted_ids).values("id", "group__name"))

    found_ids = {kw["id"] for kw in keywords}
    invalid_ids = submitted_ids - found_ids
    if invalid_ids:
        return False, f"Invalid keyword(s) for this journal: {sorted(invalid_ids)}"

    free_ids = [kw["id"] for kw in keywords if kw["group__name"] is None]
    if free_ids:
        return False, f"Keywords without a group are not allowed: {sorted(free_ids)}"

    return True, None


def jhep_keyword_selection_rule(
    keyword_weights: dict,
    journal: Journal,
    arxiv_category: str | None = None,
) -> tuple[bool, str | None]:
    """
    Validate keyword selection for JHEP submissions.

    Rules:
    - If arxiv_category == "hep-ex":
        * Exactly one keyword must be selected.
        * It must belong to the "hep-ex" group.
    - Otherwise:
        * At least 2 keywords must come from the same journal group.
        * Keywords from the "hep-ex" group are not allowed.
        * A submission must include a range of keywords defined in KEYWORDS_INTERVAL_PER_JOURNAL settin.
    """
    generic_keywords_check = True
    message: str | None = None

    keyword_range = get_keyword_range_by_journal(journal)
    submitted_ids = set(keyword_weights.keys())
    if not submitted_ids:
        return False, "You must select at least one keyword."

    keywords = list(journal.keywords.filter(id__in=submitted_ids).values("id", "group__name"))
    found_ids = {kw["id"] for kw in keywords}
    invalid_ids = submitted_ids - found_ids
    if invalid_ids:
        generic_keywords_check = False
        message = f"Invalid keyword(s) for this journal: {sorted(invalid_ids)}"

    group_map: dict[str, set[int]] = {}
    for kw in keywords:
        group = kw["group__name"]
        if group is None:
            generic_keywords_check = False
            message = f"Keyword {kw['id']} is not assigned to any group and cannot be selected."
        group_map.setdefault(group, set()).add(kw["id"])

    if generic_keywords_check:
        if arxiv_category == "hep-ex":
            if len(submitted_ids) != 1:
                generic_keywords_check = False
                message = "For hep-ex, you must select exactly 1 keyword."
            else:
                group = next(iter(group_map.keys()))
                if group != "hep-ex":
                    generic_keywords_check = False
                    message = "For hep-ex, the single keyword must belong to the hep-ex group."
        else:
            total = len(submitted_ids)

            if not (keyword_range[0] <= total <= keyword_range[1]):
                generic_keywords_check = False
                message = f"You must select between {keyword_range[0]} and {keyword_range[1]} keywords."
            elif "hep-ex" in group_map:
                generic_keywords_check = False
                message = "Keywords from the hep-ex group are not allowed for this arXiv category."
            else:
                max_in_group = max(len(ids) for ids in group_map.values())
                if max_in_group < keyword_range[0]:
                    generic_keywords_check = False
                    message = f"You must select at least {keyword_range[0]} keywords from the same journal group."  # noqa: S608

    return generic_keywords_check, message
