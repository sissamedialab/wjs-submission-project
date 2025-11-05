from collections.abc import Callable
from unittest.mock import patch

import pytest
from core.models import Account, Country
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from journal.models import Journal
from plugins.wjs_submission.models import ArticleCollaboration, Collaboration
from plugins.wjs_submission.step1 import SubmissionStep1View
from plugins.wjs_submission.views import SubmissionLastStepRedirectView
from plugins.wjs_submission.workflow import STEPS
from submission.models import (
    Article,
    ArticleAuthorOrder,
    Keyword,
    KeywordArticle,
    KeywordGroup,
    SubmissionConfiguration,
)
from utils.setting_handler import save_setting

from .conftest import _journal_factory, _user


@pytest.mark.parametrize("same_journal", [True, False])
@pytest.mark.django_db
def test_journal_check_step_1(
    journal: Journal, install_plugins: Callable, article: Article, fake_request, same_journal: bool
):
    """
    Queryset filter articles by current journal.

    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param article: Submitted article
    :type article: Article
    :param fake_request: Mock request
    :type fake_request: HttpRequest
    :param same_journal: If the article is submitted to the same journal as the one in the queryset
    :type same_journal: bool
    """
    if not same_journal:
        journal2 = _journal_factory("MIJ", journal.press, domain="testserver2.org")
        article.journal = journal2
        article.save()

    fake_request.user = article.owner
    view_obj = SubmissionStep1View()
    view_obj.kwargs = {"article_id": article.pk}
    view_obj.request = fake_request
    if not same_journal:
        assert not view_obj.get_queryset().exists()
    else:
        assert view_obj.get_queryset().exists()


@pytest.mark.parametrize("skip", [True, False])
@pytest.mark.django_db
def test_submission_context_step_1(
    journal: Journal,
    install_plugins: Callable,
    article: Article,
    fake_request,
    skip: bool,
):
    """
    View context data for step 1 include the step, the steps states and the article.

    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param article: Submitted article
    :type article: Article
    :param fake_request: Mock request
    :type fake_request: HttpRequest
    """
    view_obj = SubmissionStep1View()
    view_obj.kwargs = {"article_id": article.pk}
    view_obj.object = article
    view_obj.request = fake_request
    context = view_obj.get_context_data()
    assert context["article"] == article
    assert context["step"] == STEPS.get(1)
    assert context["steps"] == context["step"].get_steps_states(journal, article)
    for index in STEPS:
        func = context["steps"][index].step.check_function
        expected = True if func is None else func(journal)
        assert context["steps"][index].state is expected


@pytest.mark.parametrize(
    "step_number,skip",  # noqa: PT006
    [
        (1, True),
        (1, False),
        (2, True),
        (2, False),
        (3, True),
        (3, False),
        (4, True),
        (4, False),
        (5, True),
        (5, False),
        (6, True),
        (6, False),
        (7, True),
        (7, False),
        (8, True),
        (8, False),
    ],
)
@pytest.mark.django_db
def test_submission_step_skip(
    journal: Journal,
    install_plugins: Callable,
    article: Article,
    fake_request,
    step_number: int,
    skip: bool,
):
    """
    View context data for step 1 include the step, the steps states and the article.

    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param article: Submitted article
    :type article: Article
    :param fake_request: Mock request
    :type fake_request: HttpRequest
    :param step_number: Number of the step to be tested
    :type step_number: int
    :param skip: step is not active
    :type skip: bool
    """
    step = STEPS.get(step_number)
    fake_request.user = article.owner
    with patch.object(step, "check_function", return_value=not skip):
        view_obj = SubmissionStep1View()
        view_obj.kwargs = {"article_id": article.pk}
        view_obj.object = article
        view_obj.request = fake_request
        view_obj.step = step_number
        response = view_obj.get(fake_request, article_id=article.pk)
        if skip:
            # as the step is skipped, the view will redirect to the next step, in case the current step is the last one
            # it's redirected to the (temporary) step 0
            next_step_number = (step_number + 1) % 9
            assert response.status_code == 302
            assert response.headers.get("Location") == reverse(
                f"wjs_submission_{next_step_number}",
                kwargs={"article_id": article.pk},
            )
        else:
            assert response.status_code == 200


@pytest.mark.parametrize(
    "step_number",
    [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
    ],
)
@pytest.mark.django_db
def test_submission_first_incomplete_step(
    journal: Journal,
    install_plugins: Callable,
    article: Article,
    fake_request,
    step_number: int,
):
    """

    SubmissionLastStepRedirectView redirect to the first incomplete step for the article.

    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param article: Submitted article
    :type article: Article
    :param fake_request: Mock request
    :type fake_request: HttpRequest
    :param step_number: Number of the step to be tested
    :type step_number: int
    """
    fake_request.user = article.owner
    article.current_step = step_number
    article.save()
    view_obj = SubmissionLastStepRedirectView()
    view_obj.kwargs = {"article_id": article.pk}
    view_obj.object = article
    view_obj.request = fake_request
    response = view_obj.get(fake_request, article_id=article.pk)
    next_step_number = (step_number + 1) % 9
    assert response.status_code == 302
    assert response.headers.get("Location") == reverse(
        f"wjs_submission_{next_step_number}",
        kwargs={"article_id": article.pk},
    )


@pytest.mark.parametrize("authenticate", [True, False])
@pytest.mark.django_db
def test_submission_auth_only(
    client: Client, journal: Journal, install_plugins: Callable, user: Account, fake_request, authenticate: bool
):
    """
    Submittion views are only accessible to authenticated users.

    :param client: A test client instance
    :type client: Client
    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param fake_request: Mock request
    :type fake_request: HttpRequest]
    :param authenticate: If the user should be authenticated or not
    :type authenticate: bool
    """
    if authenticate:
        client.force_login(user)
        fake_request.user = user
    response = client.get(reverse("wjs_submission_1"))
    if authenticate:
        assert response.status_code == 200
    else:
        assert response.status_code == 302


@pytest.mark.parametrize("is_author", [True, False])
@pytest.mark.django_db
def test_submission_author_only(
    client: Client, article: Article, install_plugins: Callable, user: Account, fake_request, is_author: bool
):
    """
    Submission views are only accessible to authenticated users.

    :param client: A test client instance
    :type client: Client
    :param article: An instance of the article object.
    :type article: Article
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param fake_request: Mock request
    :type fake_request: HttpRequest]
    :param is_author: If the user is the article author or a different user
    :type is_author: bool
    """
    if is_author:
        client.force_login(article.owner)
    else:
        client.force_login(user)
    response = client.get(reverse("wjs_submission_1", kwargs={"article_id": article.pk}))
    if is_author:
        assert response.status_code == 200
    else:
        assert response.status_code == 404


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.django_db
def test_submission_disabled(
    client: Client, article: Article, install_plugins: Callable, user: Account, fake_request, enabled: bool
):
    """
    Submission views are only accessible when submission is enabled.

    :param client: A test client instance
    :type client: Client
    :param article: An instance of the article object.
    :type article: Article
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param fake_request: Mock request
    :type fake_request: HttpRequest]
    :param enabled: If the submission is enabled or not
    :type enabled: bool
    """
    save_setting("general", "disable_journal_submission", article.journal, not enabled)
    client.force_login(article.owner)
    response = client.get(reverse("wjs_submission_1", kwargs={"article_id": article.pk}))
    if enabled:
        assert response.status_code == 200
    else:
        assert response.status_code == 302
        assert response.headers.get("Location") == reverse("wjs_submission_closed")


@pytest.mark.parametrize(
    ("post_data", "expected_keywords", "expect_error"),
    [
        ({"keyword_1_weight": ["25"], "keyword_2_weight": ["100"]}, {1: 25, 2: 100}, False),
        ({"keyword_1_weight": ["123"]}, {}, True),
        ({}, {}, False),
        ({"keyword_x_weight": ["25"]}, {}, True),
        ({"keyword_1_weight": ["abc"]}, {}, True),
        ({"keyword_1_weight": ["25"], "keyword_2_weight": [""]}, {}, True),
        ({"keyword_1_weight": ["25"], "alien": ["field"]}, {1: 25}, False),
    ],
)
@pytest.mark.django_db
def test_keyword_handling(client, article, post_data, expected_keywords, expect_error):
    settings.WJS_KEYWORD_WEIGHT_VALIDATORS = {
        "JQUANT": ("plugins.wjs_submission.logic.always_pass",),
    }

    Keyword.objects.create(pk=1, word="keyword1", journal=article.journal)
    Keyword.objects.create(pk=2, word="keyword2", journal=article.journal)

    client.force_login(article.owner)
    url = reverse("wjs_submission_3", kwargs={"article_id": article.pk})

    if expect_error:
        with pytest.raises(ValidationError) as excinfo:
            client.post(url, {**post_data})
        exc_message = str(excinfo.value)
        assert any(msg in exc_message for msg in ["Corrupted weight data", "Invalid keyword weight data"])
        assert not KeywordArticle.objects.filter(article=article).exists()
    else:
        response = client.post(url, {**post_data})
        assert response.status_code == 302
        weights = {ka.keyword_id: ka.weight for ka in KeywordArticle.objects.filter(article=article)}
        assert weights == expected_keywords


@pytest.mark.django_db
def test_context_contains_only_journal_keyword_groups(hierarchical_keywords, client, article):
    journal = article.journal

    kw1 = Keyword.objects.create(word="kw1")
    kw2 = Keyword.objects.create(word="kw2")
    kw3 = Keyword.objects.create(word="kw3")

    g1 = KeywordGroup.objects.create(name="group1")
    g2 = KeywordGroup.objects.create(name="group2", parent_group=g1)
    g3 = KeywordGroup.objects.create(name="group3")

    kw1.group = g1
    kw1.save()
    kw2.group = g2
    kw2.save()
    kw3.group = g3
    kw3.save()

    journal.keywords.add(kw1, kw2)

    client.force_login(article.owner)
    url = reverse("wjs_submission_3", kwargs={"article_id": article.pk})
    response = client.get(url)
    groups = response.context["keywords_list"]

    assert g1 in groups
    assert g2 not in groups
    assert g3 not in groups


@pytest.mark.django_db
def test_context_contains_only_journal_keywords(client, article):
    journal = article.journal

    kw1 = Keyword.objects.create(word="kw1")
    kw2 = Keyword.objects.create(word="kw2")
    kw3 = Keyword.objects.create(word="kw3")

    g1 = KeywordGroup.objects.create(name="group1")
    g2 = KeywordGroup.objects.create(name="group2", parent_group=g1)
    g3 = KeywordGroup.objects.create(name="group3")

    kw1.group = g1
    kw1.save()
    kw2.group = g2
    kw2.save()
    kw3.group = g3
    kw3.save()

    journal.keywords.add(kw1, kw2)

    client.force_login(article.owner)
    url = reverse("wjs_submission_3", kwargs={"article_id": article.pk})
    response = client.get(url)
    keywords = response.context["keywords_list"]

    assert kw1 in keywords
    assert kw2 in keywords
    assert kw3 not in keywords


@pytest.mark.django_db
def test_keyword_article_order_preserved(client, article):
    for i in range(1, 5):
        Keyword.objects.create(word=f"kw{i}", journal=article.journal)

    post_data = {
        "keyword_1_weight": ["25"],
        "keyword_2_weight": ["50"],
        "keyword_3_weight": ["75"],
        "keyword_4_weight": ["100"],
    }

    client.force_login(article.owner)
    url = reverse("wjs_submission_3", kwargs={"article_id": article.pk})
    client.post(url, post_data)

    kws = list(KeywordArticle.objects.filter(article=article).order_by("order"))
    assert [ka.keyword_id for ka in kws] == [1, 2, 3, 4]
    assert [ka.weight for ka in kws] == [25, 50, 75, 100]
    KeywordArticle.objects.all().delete()  # not usre why we need to delete them, but otherwise the test teardown fails


@pytest.mark.django_db
def test_free_text_keywords(client, article):
    journal = article.journal
    configuration = SubmissionConfiguration.objects.get(journal=journal)
    configuration.autocomplete_keywords = True
    configuration.save()

    g1 = KeywordGroup.objects.create(name="group1")
    g2 = KeywordGroup.objects.create(name="group2")
    kw1 = Keyword.objects.create(word="kw1", journal=journal, group=g1)
    kw2 = Keyword.objects.create(word="kw2", journal=journal, group=g2)
    journal.keywords.add(kw1, kw2)

    free_keywords = [Keyword.objects.create(word=f"free{i}", journal=journal) for i in range(3)]

    post_data = {
        "keywords": [str(kw.pk) for kw in free_keywords],
        f"keyword_{kw1.pk}_weight": ["50"],
        f"keyword_{kw2.pk}_weight": ["100"],
    }

    client.force_login(article.owner)
    url = reverse("wjs_submission_3", kwargs={"article_id": article.pk})
    response = client.post(url, post_data)
    assert response.status_code == 302

    kws = KeywordArticle.objects.filter(article=article)

    created_ids = {ka.keyword_id for ka in kws}
    expected_ids = {kw1.pk, kw2.pk} | {kw.pk for kw in free_keywords}
    assert created_ids == expected_ids


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("collaboration_relation", "expect_clear"),
    [
        ("none", True),
        ("on_behalf_of", False),
    ],
)
def test_submission_step4_form_saves_country_and_authors(client, article, collaboration_relation, expect_clear):
    author1 = _user("author1")
    author2 = _user("author2")
    article.owner = _user("owner")
    article.save()

    ArticleAuthorOrder.objects.create(article=article, author=author1, order=1)
    ArticleAuthorOrder.objects.create(article=article, author=author2, order=2)

    article.correspondence_author = author1
    article.save()
    country = Country.objects.create(code="ABC", name="ABCountry")
    post_data = {
        "country": str(country.pk),
        "correspondence_author": str(author1.pk),
        "collaboration_relation": collaboration_relation,
    }
    collaboration = Collaboration.objects.create(name="Collab 1")
    ArticleCollaboration.objects.create(
        article=article,
        collaboration=collaboration,
        relation="by",
        order=Collaboration.next_collaboration_sort(article),
    )
    client.force_login(article.owner)
    url = reverse("wjs_submission_4", kwargs={"article_id": article.pk})
    response = client.post(url, post_data)
    assert response.status_code == 302

    article.refresh_from_db()
    article.submission_data.refresh_from_db()

    assert article.correspondence_author == author1
    assert Article.objects.get(pk=article.pk).submission_data.affiliation_country == country

    ids_in_order = set(ArticleAuthorOrder.objects.filter(article=article).values_list("author_id", flat=True))
    ids_on_article = set(article.authors.values_list("id", flat=True))
    assert ids_in_order == ids_on_article

    if expect_clear:
        assert article.collaborations.count() == 0
    else:
        assert article.collaborations.count() == 1
