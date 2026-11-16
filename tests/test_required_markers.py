import re
from unittest.mock import patch

import pytest
from django.urls import NoReverseMatch, reverse
from plugins.wjs_submission.keywords import KEYWORDS_INTERVAL_PER_JOURNAL
from plugins.wjs_submission.step7.forms import AddFundingForm, RevisionAddFundingForm
from submission.models import Article
from utils.setting_handler import save_setting

REQUIRED_MARKER = re.compile(r'<div class="[^"]*">(?:<hr class="mt-0">)?<strong>Required</strong></div>')


def _reverse_with_stubs(viewname, *args, **kwargs):
    """Reverse as usual, but stub URLs that belong to plugins not installed with this repo."""
    try:
        return reverse(viewname, *args, **kwargs)
    except NoReverseMatch:
        if viewname.startswith("wjs_submission"):
            raise
        return f"/stub/{viewname}/"


@pytest.mark.parametrize("form_class", [AddFundingForm, RevisionAddFundingForm])
@pytest.mark.django_db
def test_funding_statement_uses_a_four_rows_textarea(form_class):
    """The funding statement is a four rows textarea in both the submission and the revision funding forms."""
    widget = form_class.base_fields["funding_statement"].widget

    assert widget.attrs.get("rows") == 4, f"{form_class.__name__} sets the textarea rows"


@pytest.mark.parametrize(("enable_das", "enable_cas"), [(True, True), (True, False), (False, True), (False, False)])
@pytest.mark.django_db
def test_step6_required_markers_follow_the_enabled_statements(client, article: Article, enable_das, enable_cas):
    """Step 6 flags the manuscript file always, and the DAS and CAS only when they are enabled."""
    article.current_step = 6
    article.save()
    save_setting("wjs_submission", "enable_das", article.journal, enable_das)
    save_setting("wjs_submission", "enable_cas", article.journal, enable_cas)

    client.force_login(article.owner)
    response = client.get(reverse("wjs_submission_6", kwargs={"article_id": article.pk}))

    assert response.status_code == 200, "step 6 is rendered"
    assert len(REQUIRED_MARKER.findall(response.content.decode())) == 1 + enable_das + enable_cas, (
        "the manuscript file marker plus one marker for each enabled statement"
    )


@pytest.mark.django_db
def test_add_funding_modal_asks_for_the_large_size(client, article: Article):
    """The funding modal declares data-modal-size="lg", which the theme stylesheet uses to widen #htmxModal."""
    client.force_login(article.owner)
    response = client.get(reverse("add-funding", kwargs={"article_id": article.pk}))

    assert response.status_code == 200, "the funding modal is rendered"
    assert 'data-modal-size="lg"' in response.content.decode(), "the modal requests the large size"


@pytest.mark.parametrize(
    ("hierarchical", "minimum", "expected"),
    [(True, 1, True), (True, 0, False), (False, 1, False)],
)
@pytest.mark.django_db
def test_step3_weights_required_marker_is_rendered_hidden(
    client, article: Article, request, monkeypatch, hierarchical, minimum, expected
):
    """Step 3 renders a keywords weight marker that is hidden until the weights are shown."""
    if hierarchical:
        request.getfixturevalue("hierarchical_keywords")
    monkeypatch.setitem(KEYWORDS_INTERVAL_PER_JOURNAL, None, (minimum, 3))
    monkeypatch.setitem(KEYWORDS_INTERVAL_PER_JOURNAL, article.journal.code, (minimum, 3))

    client.force_login(article.owner)
    html = client.get(reverse("wjs_submission_3", kwargs={"article_id": article.pk})).content.decode()

    marker = re.search(
        r'<div class="([^"]*keywords-weight-required[^"]*)">(?:<hr class="mt-0">)?<strong>Required</strong></div>',
        html,
    )
    assert bool(marker) is expected, "the weight marker is rendered only for hierarchical journals with a minimum"
    if expected:
        assert "d-none" in marker.group(1).split(), "the weight marker starts hidden"


@pytest.mark.django_db
def test_step4_does_not_flag_the_co_authors_as_required(client, article: Article):
    """
    Step 4 does not flag the co-authors as required.

    Co-authors are optional (a single-author submission is valid): only the author list and the corresponding author
    are required, so the co-authors search section carries no "Required" marker.
    """
    article.current_step = 4
    article.save()

    client.force_login(article.owner)
    # The page links to URLs of other plugins (e.g. search-typeahead) that are not available in this repo
    # ({% url %} resolves reverse either from its own module or from django.urls, depending on the Django version)
    with (
        patch("django.urls.reverse", _reverse_with_stubs),
        patch("django.template.defaulttags.reverse", _reverse_with_stubs, create=True),
    ):
        response = client.get(reverse("wjs_submission_4", kwargs={"article_id": article.pk}))

    assert response.status_code == 200, "step 4 is rendered"
    content = response.content.decode()
    co_authors_section = content.split('id="authors-section"')[1].split('id="selected-authors-wrapper"')[0]
    assert "Required" not in co_authors_section, "the co-authors search section is not flagged as required"
    assert len(REQUIRED_MARKER.findall(content)) == 1, "only the corresponding author is flagged as required"
