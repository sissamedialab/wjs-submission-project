"""Tests for the article search and filters shared by the advanced admin article pages."""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory
from identifiers.models import Identifier
from plugins.wjs_submission.advanced_admin.advanced_admin import CollaborationAdmin, CollaborationProxy
from submission.models import Article
from wjs.advanced_admin.admin import ArticleAdmin, advanced_admin_site

from .helpers import get_changelist

Account = get_user_model()

ARTICLE_FILTERS = [
    "journal",
    "stage",
    "articleworkflow__state",
    "is_import",
    "peer_reviewed",
    "date_submitted",
    "date_accepted",
    "date_declined",
    "date_published",
]


def _account(email: str, first_name: str, last_name: str) -> Account:
    return Account.objects.create(username=email, email=email, first_name=first_name, last_name=last_name)


@pytest.fixture
def searchable_article(article):
    """Prepare an article with a known title, preprint id, correspondence author and owner."""
    article.title = "Interpreting the signals of science"
    article.correspondence_author = _account("m.rudzinski@example.org", "Marta", "Rudziński")
    article.owner = _account("munizziwilliam@example.org", "William", "Munizzi")
    article.save()
    Identifier.objects.create(article=article, id_type="preprintid", identifier="JCOM_4515")
    return article


def _request(admin_user, params=None):
    request = RequestFactory().get("/", params or {})
    request.user = admin_user
    return request


def _search(admin_user, term):
    model_admin = ArticleAdmin(Article, advanced_admin_site)
    queryset, _ = model_admin.get_search_results(_request(admin_user), Article.objects.all(), term)
    return queryset


@pytest.mark.django_db
def test_unaccent_extension_available():
    """The unaccent extension is installed in the test database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT unaccent(%s)", ["Rudziński"])
        assert cursor.fetchone()[0] == "Rudzinski", "unaccent must strip diacritics"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "term",
    [
        "{pk}",
        "JQuant_{pk}",
        "JCOM_4515",
        "Interpreting",
        "signals of science",
        "m.rudzinski@example.org",
        "Rudziński",
        "Rudzinski",
        "rudzinski",
        "Marta",
        "Munizzi",
        "munizziwilliam@example.org",
        "William",
    ],
)
def test_article_search_finds(searchable_article, admin, term):
    """Each searchable field (pk, label, identifier, title, author and owner data) finds the article."""
    term = term.format(pk=searchable_article.pk)
    assert searchable_article in _search(admin, term), f"{term!r} must find the article"


@pytest.mark.django_db
def test_article_search_stored_plain_typed_accented(searchable_article, admin):
    """A name stored without diacritics is found by a term typed with them."""
    searchable_article.owner.last_name = "Rudzinski"
    searchable_article.owner.save()
    searchable_article.correspondence_author.last_name = "Other"
    searchable_article.correspondence_author.save()
    assert searchable_article in _search(admin, "Rudziński"), "accented term must find the plain stored name"


@pytest.mark.django_db
def test_article_search_pk_is_exact(searchable_article, admin):
    """The pk match is exact: a longer number containing the pk does not match."""
    term = f"9{searchable_article.pk}9"
    assert searchable_article not in _search(admin, term), "pk search must be exact, not substring"


@pytest.mark.django_db
def test_article_search_label_also_matches_identifier(searchable_article, admin):
    """A "<journal code>_<pk>" term also finds papers whose identifier contains it."""
    other = Article.objects.create(title="Another paper", journal=searchable_article.journal)
    Identifier.objects.create(article=other, id_type="preprintid", identifier=f"JCOM_{searchable_article.pk}")
    result = _search(admin, f"JCOM_{searchable_article.pk}")
    assert searchable_article in result, "the label must find the paper with that pk"
    assert other in result, "the label must also find the paper with that identifier"


@pytest.mark.django_db
def test_article_search_blank_term_returns_all(searchable_article, admin):
    """A blank search term returns the whole queryset."""
    assert set(_search(admin, "  ")) == set(Article.objects.all()), "blank term must not filter"


@pytest.mark.django_db
def test_article_search_no_correspondence_author(searchable_article, admin):
    """A paper without correspondence author is still found by title."""
    searchable_article.correspondence_author = None
    searchable_article.save()
    assert searchable_article in _search(admin, "Interpreting"), "nullable author must not hide the paper"


@pytest.mark.django_db
def test_article_changelist_no_duplicates(searchable_article, admin):
    """A paper with two matching identifiers is listed once."""
    Identifier.objects.create(article=searchable_article, id_type="doi", identifier="JCOM_4515_v2")
    model_admin = ArticleAdmin(Article, advanced_admin_site)
    changelist = get_changelist(model_admin, _request(admin, {"q": "JCOM_4515"}))
    assert changelist.result_count == 1, f"expected one row, got {changelist.result_count}"


@pytest.mark.django_db
def test_article_list_filter(admin):
    """The Articles page offers the shared filters."""
    model_admin = ArticleAdmin(Article, advanced_admin_site)
    assert model_admin.get_list_filter(_request(admin)) == ARTICLE_FILTERS, "unexpected Articles filters"


@pytest.mark.django_db
def test_article_admin_passes_autocomplete_checks():
    """ArticleAdmin declares search_fields, required by the article autocompletes on the advanced admin (E040)."""
    errors = [
        error for error in CollaborationAdmin(CollaborationProxy, advanced_admin_site).check() if error.is_serious()
    ]
    assert errors == [], f"admin system check errors: {errors}"
