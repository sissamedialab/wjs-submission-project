import pytest
from django.db.models import QuerySet
from django.utils import timezone
from plugins.wjs_submission.keywords import (
    get_keywords_by_journal,
    get_keywords_by_journal_and_arxiv_category,
    jhep_keyword_selection_rule,
    jquant_keyword_selection_rule,
)
from submission.models import Keyword, KeywordGroup


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("keyword_setup", "weights", "assign_group", "expected_ok"),
    [
        # valid 2 keyword with group -> fail
        (["kw1"], [25], True, False),
        # valid 2 keywords with group -> should pass
        (["kw1", "kw2"], [25, 50], True, True),
        # too few keywords -> fail
        ([], [], True, False),
        # free keywords (no group) -> fail
        (["kw1", "kw2"], [25, 50], False, False),
        # 3 keywords, all grouped -> pass
        (["kw1", "kw2", "kw3"], [25, 50, 75], True, True),
        # 4 keywords, one free -> fail
        (["kw1", "kw2", "kw3", "kw4"], [25, 50, 75, 100], False, False),
        # 4 keywords, all grouped -> should pass
        (["kw1", "kw2", "kw3", "kw4"], [25, 50, 75, 100], True, True),
        # 5 keywords -> fail
        (["kw1", "kw2", "kw3", "kw4", "kw5"], [25, 50, 75, 100, 25], True, False),
    ],
)
def test_jquant_rule(jquant_journal, keyword_setup, weights, assign_group, expected_ok):
    journal = jquant_journal
    keyword_weights = {}

    for name, weight in zip(keyword_setup, weights, strict=False):
        group = KeywordGroup.objects.create(name="group1") if assign_group else None
        kw = Keyword.objects.create(word=name, group=group)
        journal.keywords.add(kw)
        keyword_weights[kw.id] = weight

    ok, error = jquant_keyword_selection_rule(keyword_weights, journal=journal)
    assert ok == expected_ok
    if expected_ok:
        assert error is None
    else:
        assert error is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("keyword_setup", "weights", "assign_group", "arxiv_category", "expected_ok"),
    [
        # hep-ex: 1 keyword in hep-ex -> should pass
        (["kw1"], [25], True, "hep-ex", True),
        # hep-ph: 1 keyword -> should pass
        (["kw1"], [25], True, "hep-ph", True),
        # hep-ex: 2 keywords -> fail (must select exactly 1)
        (["kw1", "kw2"], [25, 50], True, "hep-ex", False),
        # hep-ph: 2 keywords same group -> should pass
        (["kw1", "kw2"], [25, 50], True, "hep-ph", True),
        # hep-ph: 3 keywords, 2 in main group + 1 in other group -> should pass
        (["kw1", "kw2", "kw3"], [25, 50, 75], True, "hep-ph", True),
        # hep-ph: 4 keywords, 2 in main group + 2 in other groups -> should fail
        (["kw1", "kw2", "kw3", "kw4"], [25, 50, 75, 100], True, "hep-ph", True),
    ],
)
def test_jhep_rule(jhep_journal, keyword_setup, weights, assign_group, arxiv_category, expected_ok):
    journal = jhep_journal
    keyword_weights = {}

    for i, (name, weight) in enumerate(zip(keyword_setup, weights, strict=False), start=1):
        if assign_group:
            if arxiv_category == "hep-ex":
                group = KeywordGroup.objects.get_or_create(name="hep-ex")[0]
            elif i <= 2:
                main_group = KeywordGroup.objects.get_or_create(name="group_main")[0]
                group = main_group
            else:
                group = KeywordGroup.objects.create(name=f"group{i}")
        else:
            group = None

        kw = Keyword.objects.create(word=name, group=group)
        journal.keywords.add(kw)
        keyword_weights[kw.id] = weight

    ok, text = jhep_keyword_selection_rule(keyword_weights, journal=journal, arxiv_category=arxiv_category)
    assert ok == expected_ok
    if expected_ok:
        assert text is None
    else:
        assert text


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("keyword_setup", "group_names", "expected_groups"),
    [
        # 2 keywords, each in a separate group -> returns both top-level groups
        (["kw1", "kw2"], ["group1", "group2"], ["group1", "group2"]),
        # 2 keywords in the same group -> only one top-level group returned
        (["kw1", "kw2"], ["group1", "group1"], ["group1"]),
        # 1 keyword in 1 group -> single top-level group
        (["kw1"], ["group1"], ["group1"]),
        # 3 keywords, 2 grouped, 1 ungrouped -> only grouped top-level groups returned
        (["kw1", "kw2", "kw3"], ["group1", "group2", None], ["group1", "group2"]),
        # all keywords ungrouped -> no top-level groups returned
        (["kw1", "kw2"], [None, None], []),
    ],
)
def test_get_keywords_by_journal_groups(jquant_journal, keyword_setup, group_names, expected_groups):
    """
    Test get_keywords_by_journal returns only top-level groups linked to grouped keywords.

    Group creation logic:
    - Each keyword is assigned the group specified in group_names.
    - None in group_names means the keyword is ungrouped.
    - Keywords are added to the journal.
    """
    journal = jquant_journal

    for name, group_name in zip(keyword_setup, group_names, strict=False):
        group = KeywordGroup.objects.get_or_create(name=group_name)[0] if group_name else None
        kw = Keyword.objects.create(word=name, group=group)
        journal.keywords.add(kw)

    qs = get_keywords_by_journal(journal)
    actual_groups = list(qs.values_list("name", flat=True))

    assert all(g.parent_group is None for g in qs)
    assert sorted(actual_groups) == sorted(expected_groups)
    assert isinstance(qs, QuerySet)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("keyword_setup", "group_names", "arxiv_category", "expected_groups"),
    [
        # hep-ex, 1 keyword in hep-ex -> only hep-ex returned
        (["kw1"], ["hep-ex"], "hep-ex", ["hep-ex"]),
        # hep-ex, multiple keywords in hep-ex -> only hep-ex returned
        (["kw1", "kw2"], ["hep-ex", "hep-ex"], "hep-ex", ["hep-ex"]),
        # hep-ph, 2 keywords in different top-level groups -> both returned
        (["kw1", "kw2"], ["group_main", "group2"], "hep-ph", ["group_main", "group2"]),
        # hep-ph, 1 keyword in hep-ex (should be excluded) -> empty
        (["kw1"], ["hep-ex"], "hep-ph", []),
        # mixed grouped and ungrouped, hep-ph -> only grouped top-level groups returned
        (["kw1", "kw2", "kw3"], ["group_main", None, "group3"], "hep-ph", ["group_main", "group3"]),
        # all ungrouped -> no top-level groups
        (["kw1", "kw2"], [None, None], "hep-ph", []),
        # 3 keywords in multiple groups -> return all top-level groups linked to grouped keywords
        (["kw1", "kw2", "kw3"], ["group_main", "group2", "group3"], "hep-ph", ["group_main", "group2", "group3"]),
    ],
)
def test_get_keywords_by_journal_and_arxiv_category_groups(
    jhep_journal, keyword_setup, group_names, arxiv_category, expected_groups
):
    """
    Test get_keywords_by_journal_and_arxiv_category.

    Ensures only top-level groups linked to keywords are returned, respecting
    arXiv category rules:

    - 'hep-ex': only keywords in the 'hep-ex' group are included.
    - Other categories: the 'hep-ex' group is excluded.
    - Ungrouped keywords are ignored.
    """
    journal = jhep_journal

    for name, group_name in zip(keyword_setup, group_names, strict=False):
        group = KeywordGroup.objects.get_or_create(name=group_name)[0] if group_name else None
        kw = Keyword.objects.create(word=name, group=group)
        journal.keywords.add(kw)

    qs = get_keywords_by_journal_and_arxiv_category(journal, arxiv_category=arxiv_category)
    actual_groups = list(qs.values_list("name", flat=True))

    assert all(g.parent_group is None for g in qs)
    assert sorted(actual_groups) == sorted(expected_groups)
    assert isinstance(qs, QuerySet)


@pytest.mark.django_db
def test_get_keywords_by_journal_excludes_deactivated_flat(journal):
    """Deactivated keywords are not offered on a journal with flat (non-hierarchical) keywords."""
    active = Keyword.objects.create(word="active-kw")
    stale = Keyword.objects.create(word="stale-kw", deactivated=timezone.now())
    journal.keywords.add(active, stale)

    assert list(get_keywords_by_journal(journal)) == [active], "only the active keyword is offered"


@pytest.mark.django_db
def test_get_keywords_by_journal_excludes_deactivated_hierarchical(jquant_journal):
    """
    Deactivated keywords are dropped from the groups they belong to.

    A group whose keywords are all deactivated disappears from the result entirely.
    """
    journal = jquant_journal
    live_group = KeywordGroup.objects.create(name="live-group")
    dead_group = KeywordGroup.objects.create(name="dead-group")

    active = Keyword.objects.create(word="active-kw", group=live_group)
    stale = Keyword.objects.create(word="stale-kw", group=live_group, deactivated=timezone.now())
    only_stale = Keyword.objects.create(word="only-stale-kw", group=dead_group, deactivated=timezone.now())
    journal.keywords.add(active, stale, only_stale)

    groups = list(get_keywords_by_journal(journal))

    assert [group.name for group in groups] == ["live-group"], "the fully deactivated group is dropped"
    assert list(groups[0].keywords.all()) == [active], "the deactivated keyword is dropped from its group"


@pytest.mark.django_db
def test_get_keywords_by_journal_excludes_deactivated_in_subgroups(jquant_journal):
    """Deactivated keywords are dropped from subgroups, and emptied subgroups are not offered."""
    journal = jquant_journal
    parent = KeywordGroup.objects.create(name="parent-group")
    live_subgroup = KeywordGroup.objects.create(name="live-subgroup", parent_group=parent, order=1)
    dead_subgroup = KeywordGroup.objects.create(name="dead-subgroup", parent_group=parent, order=2)

    active = Keyword.objects.create(word="active-kw", group=live_subgroup)
    stale = Keyword.objects.create(word="stale-kw", group=live_subgroup, deactivated=timezone.now())
    only_stale = Keyword.objects.create(word="only-stale-kw", group=dead_subgroup, deactivated=timezone.now())
    journal.keywords.add(active, stale, only_stale)

    groups = list(get_keywords_by_journal(journal))

    assert [group.name for group in groups] == ["parent-group"], "the parent group is still offered"
    subgroups = list(groups[0].keywordgroup_set.all())
    assert [subgroup.name for subgroup in subgroups] == ["live-subgroup"], "the emptied subgroup is dropped"
    assert list(subgroups[0].keywords.all()) == [active], "the deactivated keyword is dropped from its subgroup"


@pytest.mark.django_db
def test_get_keywords_by_journal_keywords_are_journal_scoped(jquant_journal, journal):
    """Keywords offered inside a group belong to the requested journal only."""
    shared_group = KeywordGroup.objects.create(name="shared-group")
    ours = Keyword.objects.create(word="ours-kw", group=shared_group)
    theirs = Keyword.objects.create(word="theirs-kw", group=shared_group)
    jquant_journal.keywords.add(ours)
    journal.keywords.add(theirs)

    groups = list(get_keywords_by_journal(jquant_journal))

    assert [group.name for group in groups] == ["shared-group"], "the shared group is offered"
    assert list(groups[0].keywords.all()) == [ours], "another journal's keyword must not leak into the group"


@pytest.mark.django_db
@pytest.mark.parametrize(("arxiv_category", "group_name"), [("hep-ex", "hep-ex"), ("hep-ph", "group_main")])
def test_get_keywords_by_journal_and_arxiv_category_excludes_deactivated(jhep_journal, arxiv_category, group_name):
    """Deactivated keywords are dropped for both arXiv category branches."""
    journal = jhep_journal
    group = KeywordGroup.objects.create(name=group_name)

    active = Keyword.objects.create(word="active-kw", group=group)
    stale = Keyword.objects.create(word="stale-kw", group=group, deactivated=timezone.now())
    journal.keywords.add(active, stale)

    groups = list(get_keywords_by_journal_and_arxiv_category(journal, arxiv_category=arxiv_category))

    assert [returned.name for returned in groups] == [group_name], "the group is still offered"
    assert list(groups[0].keywords.all()) == [active], "the deactivated keyword is dropped from its group"


@pytest.mark.django_db
def test_get_keywords_by_journal_and_arxiv_category_drops_fully_deactivated_group(jhep_journal):
    """A group whose keywords are all deactivated is not offered for JHEP."""
    journal = jhep_journal
    live_group = KeywordGroup.objects.create(name="group_main")
    dead_group = KeywordGroup.objects.create(name="group_dead")

    active = Keyword.objects.create(word="active-kw", group=live_group)
    only_stale = Keyword.objects.create(word="only-stale-kw", group=dead_group, deactivated=timezone.now())
    journal.keywords.add(active, only_stale)

    groups = list(get_keywords_by_journal_and_arxiv_category(journal, arxiv_category="hep-ph"))

    assert [group.name for group in groups] == ["group_main"], "the fully deactivated group is dropped"
    assert list(groups[0].keywords.all()) == [active], "only the active keyword is offered"


@pytest.mark.django_db
def test_get_keywords_by_journal_prefetches_the_whole_group_tree(django_assert_num_queries, jquant_journal):
    """
    Walking the returned group tree must not issue a query per group.

    This pins the prefetching in place: a refactor dropping it would both reintroduce an N+1 and
    silently stop filtering the keywords the step 3 template actually renders.
    """
    journal = jquant_journal
    for index in range(3):
        parent = KeywordGroup.objects.create(name=f"parent-{index}")
        subgroup = KeywordGroup.objects.create(name=f"subgroup-{index}", parent_group=parent)
        keyword = Keyword.objects.create(word=f"kw-{index}", group=subgroup)
        journal.keywords.add(keyword)

    # One query for the groups themselves, plus one per prefetched relation.
    with django_assert_num_queries(4):
        for group in get_keywords_by_journal(journal):
            for subgroup in group.keywordgroup_set.all():
                list(subgroup.keywords.all())
            list(group.keywords.all())
