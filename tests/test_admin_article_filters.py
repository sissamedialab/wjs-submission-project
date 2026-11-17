"""Tests for the filters shared by the Articles and Article submissions pages of the advanced admin."""

from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.utils.timezone import localtime, now
from plugins.wjs_submission.advanced_admin.advanced_admin import ArticleSubmissionAdmin
from plugins.wjs_submission.models import ArticleSubmission
from submission.models import STAGE_PUBLISHED, Article
from wjs.advanced_admin.admin import ArticleAdmin, advanced_admin_site

from .helpers import get_changelist

# admin class, model, lookup prefix to the article, row of the page for an article
PAGES = {
    "articles": (ArticleAdmin, Article, "", lambda article: article),
    "submissions": (
        ArticleSubmissionAdmin,
        ArticleSubmission,
        "article__",
        lambda article: ArticleSubmission.objects.get_or_create(article=article)[0],
    ),
}
DATE_FIELDS = ("date_submitted", "date_accepted", "date_declined", "date_published")


def _past_7_days(field):
    """Return the query parameters of the "Past 7 days" choice of a date filter, as Django builds them."""
    today = localtime(now()).replace(hour=0, minute=0, second=0, microsecond=0)
    return {f"{field}__gte": str(today - timedelta(days=7)), f"{field}__lt": str(today + timedelta(days=1))}


FILTER_CASES = [
    pytest.param({"stage": STAGE_PUBLISHED}, {"stage__exact": STAGE_PUBLISHED}, id="stage"),
    pytest.param({"is_import": True}, {"is_import__exact": "1"}, id="is_import"),
    pytest.param({"peer_reviewed": False}, {"peer_reviewed__exact": "0"}, id="peer_reviewed"),
    *(pytest.param({field: now() - timedelta(days=2)}, _past_7_days(field), id=field) for field in DATE_FIELDS),
]


@pytest.fixture
def matching_and_other(article):
    """Return the article the filter must keep and an article left with the default values, which it must drop."""
    other = Article.objects.create(title="Another paper", journal=article.journal)
    return article, other


def _filtered(admin_user, page, params):
    """
    Return the rows of a page with the filter query parameters applied, as the changelist does.

    Django applies a lookup on a model field even without a filter for it, so the parameters are first checked
    against those the page's filters expect.
    """
    admin_class, model, prefix, _row = PAGES[page]
    query = {f"{prefix}{key}": value for key, value in params.items()}
    request = RequestFactory().get("/", query)
    request.user = admin_user
    changelist = get_changelist(admin_class(model, advanced_admin_site), request)
    expected = {param for spec in changelist.filter_specs for param in spec.expected_parameters()}
    assert set(query) <= expected, f"{sorted(set(query) - expected)} belong to no filter of the page"
    return changelist.queryset


@pytest.mark.django_db
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize(("values", "params"), FILTER_CASES)
def test_article_filter_applies(matching_and_other, admin, page, values, params):
    """Each article filter keeps the paper with the chosen value and drops the others, on both pages."""
    matching, other = matching_and_other
    for field, value in values.items():
        setattr(matching, field, value)
    matching.save()
    row = PAGES[page][3]

    result = _filtered(admin, page, params)

    assert row(matching) in result, f"{params} must keep the matching paper"
    assert row(other) not in result, f"{params} must drop the other paper"


@pytest.mark.django_db
@pytest.mark.parametrize("page", PAGES)
def test_article_journal_filter_applies(matching_and_other, jquant_journal, admin, page):
    """The journal filter keeps only the papers of the chosen journal, on both pages."""
    matching, other = matching_and_other
    matching.journal = jquant_journal
    matching.save()
    row = PAGES[page][3]

    result = _filtered(admin, page, {"journal__id__exact": jquant_journal.pk})

    assert row(matching) in result, "the journal filter must keep the paper of the chosen journal"
    assert row(other) not in result, "the journal filter must drop the papers of other journals"
