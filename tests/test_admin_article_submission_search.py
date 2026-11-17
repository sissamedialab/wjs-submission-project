"""Tests for ArticleSubmission advanced admin search."""

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from identifiers.models import Identifier
from plugins.wjs_submission.advanced_admin.advanced_admin import ArticleSubmissionAdmin
from plugins.wjs_submission.models import ArticleSubmission

Account = get_user_model()


@pytest.fixture
def article_submission(article):
    """Create an ArticleSubmission for an article with a known title and preprint id."""
    article.title = "Interpreting the signals of science"
    article.save()
    Identifier.objects.create(article=article, id_type="preprintid", identifier="JCOM_4515")
    submission, _ = ArticleSubmission.objects.get_or_create(article=article)
    return submission


def _search(admin_user, term):
    request = RequestFactory().get("/")
    request.user = admin_user
    model_admin = ArticleSubmissionAdmin(ArticleSubmission, django_admin.site)
    queryset, _ = model_admin.get_search_results(request, ArticleSubmission.objects.all(), term)
    return queryset


@pytest.mark.django_db
def test_article_submission_search_by_title_word(article_submission, admin):
    """A word from the article title finds the article submission."""
    assert article_submission in _search(admin, "Interpreting"), "title word must find the article submission"


@pytest.mark.django_db
@pytest.mark.parametrize("label", ["{pk}", "JQuant_{pk}", "JCOM_{pk}"])
def test_article_submission_search_by_article_pk(article_submission, admin, label):
    """The article pk, bare or as the "<journal code>_<pk>" label shown in wjs-review, finds the submission."""
    term = label.format(pk=article_submission.article.pk)
    assert article_submission in _search(admin, term), f"{term!r} must find the article submission"


@pytest.mark.django_db
def test_article_submission_search_by_article_pk_is_exact(article_submission, admin):
    """The pk match is exact: a longer number containing the pk does not match."""
    term = f"9{article_submission.article.pk}9"
    assert article_submission not in _search(admin, term), "pk search must be exact, not substring"


@pytest.mark.django_db
def test_article_submission_search_by_identifier(article_submission, admin):
    """The numeric part of the preprint id still finds the article submission."""
    assert article_submission in _search(admin, "4515"), "preprint id must find the article submission"


@pytest.fixture
def searchable_submission(article_submission):
    """Give the submission's article a correspondence author and an owner with known data."""
    article = article_submission.article
    article.correspondence_author = Account.objects.create(
        username="m.rudzinski@example.org", email="m.rudzinski@example.org", first_name="Marta", last_name="Rudziński"
    )
    article.owner = Account.objects.create(
        username="munizziwilliam@example.org",
        email="munizziwilliam@example.org",
        first_name="William",
        last_name="Munizzi",
    )
    article.save()
    return article_submission


@pytest.mark.django_db
@pytest.mark.parametrize(
    "term",
    [
        "Interpreting",
        "signals of science",
        "JCOM_4515",
        "m.rudzinski@example.org",
        "Rudziński",
        "Rudzinski",
        "Marta",
        "Munizzi",
        "munizziwilliam@example.org",
        "William",
    ],
)
def test_article_submission_search_finds(searchable_submission, admin, term):
    """Title, identifier, correspondence author and owner data find the article submission."""
    assert searchable_submission in _search(admin, term), f"{term!r} must find the article submission"


@pytest.mark.django_db
def test_article_submission_list_filter(admin):
    """The Article submissions page offers the shared filters, relative to the article."""
    request = RequestFactory().get("/")
    request.user = admin
    model_admin = ArticleSubmissionAdmin(ArticleSubmission, django_admin.site)
    assert model_admin.get_list_filter(request) == [
        "article__journal",
        "article__stage",
        "article__articleworkflow__state",
        "article__is_import",
        "article__peer_reviewed",
        "article__date_submitted",
        "article__date_accepted",
        "article__date_declined",
        "article__date_published",
    ], "unexpected Article submissions filters"
