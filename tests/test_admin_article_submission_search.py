"""Tests for ArticleSubmission advanced admin search."""

import pytest
from django.contrib import admin as django_admin
from django.test import RequestFactory
from identifiers.models import Identifier
from plugins.wjs_submission.advanced_admin.advanced_admin import ArticleSubmissionAdmin
from plugins.wjs_submission.models import ArticleSubmission


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
