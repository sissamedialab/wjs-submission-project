"""
Step 8 serializes submissions of the same article (specs#3233).

Two overlapping POSTs (e.g. a double click on "Submit") must not run the submission twice, and a late POST for an
article that has already been submitted is sent to the status page.

The events raised at the end of the submission are subscribed to by other plugins (wjs_review), which are not
installed here: ``raise_event`` is patched and used to count the submissions.
"""

import threading
from collections.abc import Callable
from unittest.mock import patch

import pytest
from core.models import Account
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import Http404, HttpResponse
from django.test import Client
from django.urls import reverse
from events import logic as event_logic
from plugins.wjs_submission.models import AccessMode
from plugins.wjs_submission.step8.views import SubmissionStep8View
from press.models import Press
from submission.models import STAGE_UNSUBMITTED, Article

from .conftest import _journal_factory
from .utils import create_rich_fake_request

ALREADY_SUBMITTED_MESSAGE = "This submission has already been completed."
WAIT = 60


def _ready_for_step8(article: Article) -> Article:
    """Set the access mode, which step 8 requires to be rendered and submitted."""
    article.submission_data.access_mode = AccessMode.objects.filter(parameters__journal=article.journal).first()
    article.submission_data.save()
    return article


def _submissions(raise_event) -> int:
    """Count the first submissions raised through the patched ``raise_event``."""
    return sum(1 for call in raise_event.call_args_list if call.args[0] == event_logic.Events.ON_ARTICLE_SUBMITTED)


def _step8_url(article: Article) -> str:
    return reverse("wjs_submission_8", kwargs={"article_id": article.pk})


def _status_url(article: Article) -> str:
    return reverse("wjs_submission_0", kwargs={"article_id": article.pk})


@pytest.mark.django_db
def test_late_resubmit_redirects_to_status_page(client: Client, article: Article, install_plugins: Callable):
    """A POST for an article that has already been submitted does not submit it again."""
    _ready_for_step8(article)
    client.force_login(article.owner)
    with patch.object(event_logic.Events, "raise_event") as raise_event:
        first = client.post(_step8_url(article))
        assert first.status_code == 302
        article.refresh_from_db()
        date_submitted = article.date_submitted

        response = client.post(_step8_url(article))

    assert response.status_code == 302
    assert response.headers["Location"] == _status_url(article)
    messages = [str(message) for message in get_messages(response.wsgi_request)]
    assert ALREADY_SUBMITTED_MESSAGE in messages
    assert _submissions(raise_event) == 1
    article.refresh_from_db()
    assert article.date_submitted == date_submitted


@pytest.mark.django_db
def test_resubmit_by_coauthor_is_404(client: Client, article: Article, coauthor: Account, install_plugins: Callable):
    """Only owner and correspondence author can submit: the "already submitted" redirect is not shown to others."""
    _ready_for_step8(article)
    client.force_login(article.owner)
    with patch.object(event_logic.Events, "raise_event"):
        assert client.post(_step8_url(article)).status_code == 302
        client.force_login(coauthor)

        response = client.post(_step8_url(article))

    assert response.status_code == 404


@pytest.mark.django_db
def test_resubmit_other_journal_is_404(article: Article, press: Press, settings, install_plugins: Callable):
    """The "already submitted" redirect is limited to the articles of the current journal."""
    _ready_for_step8(article)
    with patch.object(event_logic.Events, "raise_event"):
        request = create_rich_fake_request(article.journal, settings, user=article.owner)
        request.method = "POST"
        assert SubmissionStep8View.as_view()(request, article_id=article.pk).status_code == 302
        other_journal = _journal_factory("OTHER", press)
        request = create_rich_fake_request(other_journal, settings, user=article.owner)
        request.method = "POST"

        with pytest.raises(Http404):
            SubmissionStep8View.as_view()(request, article_id=article.pk)


@pytest.mark.django_db
def test_validation_error_rerenders_form(client: Client, article: Article, install_plugins: Callable):
    """A ValidationError raised by the submission re-renders the form, the article is not submitted."""
    _ready_for_step8(article)
    client.force_login(article.owner)
    with (
        patch(
            "plugins.wjs_submission.step8.forms.CompleteSubmission.run",
            side_effect=ValidationError("Author did not confirm submission requirements"),
        ),
        patch(
            "plugins.wjs_submission.step8.views.SubmissionStep8View.render_to_response",
            return_value=HttpResponse("rendered"),
        ) as render,
    ):
        response = client.post(_step8_url(article))

    assert response.status_code == 200
    assert response.content == b"rendered"
    form = render.call_args.args[0]["form"]
    assert "Author did not confirm submission requirements" in form.non_field_errors()
    article.refresh_from_db()
    assert article.stage == STAGE_UNSUBMITTED


def _post_step8(article: Article, settings, results: dict, key: str):
    """Run the step-8 view as a POST from the article owner, in its own DB connection."""
    try:
        request = create_rich_fake_request(article.journal, settings, user=article.owner)
        request.method = "POST"
        results[key] = SubmissionStep8View.as_view()(request, article_id=article.pk)
    except Exception as e:  # noqa: BLE001
        results[key] = e
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
def test_concurrent_first_submissions_are_serialized(article: Article, settings, install_plugins: Callable):
    """
    The second of two overlapping POSTs waits for the first one and then does not submit the article again.

    Request B is paused while it holds the article lock; request A, started meanwhile, must wait for it.
    """
    _ready_for_step8(article)
    b_paused = threading.Event()
    release_b = threading.Event()
    original_get_form_kwargs = SubmissionStep8View.get_form_kwargs

    def get_form_kwargs(view):
        kwargs = original_get_form_kwargs(view)
        if threading.current_thread().name == "request-B":
            b_paused.set()
            assert release_b.wait(WAIT)
        return kwargs

    results = {}
    with (
        patch.object(event_logic.Events, "raise_event") as raise_event,
        patch.object(SubmissionStep8View, "get_form_kwargs", get_form_kwargs),
    ):
        thread_b = threading.Thread(target=_post_step8, args=(article, settings, results, "B"), name="request-B")
        thread_b.start()
        assert b_paused.wait(WAIT), f"request B never reached get_form_kwargs: {results.get('B')!r}"
        thread_a = threading.Thread(target=_post_step8, args=(article, settings, results, "A"), name="request-A")
        thread_a.start()
        thread_a.join(3)
        a_was_blocked = thread_a.is_alive()
        release_b.set()
        thread_b.join(WAIT)
        thread_a.join(WAIT)

    assert a_was_blocked, "request A must wait for the article lock held by request B"
    for key in ("A", "B"):
        assert not isinstance(results[key], Exception), f"{key}: {results[key]!r}"
        assert results[key].status_code == 302
        # The journal URL prefix is thread-local: the worker threads build URLs without it
        assert results[key].url.endswith(f"/submission/{article.pk}/0/")
    assert _submissions(raise_event) == 1
    article.refresh_from_db()
    assert article.stage != STAGE_UNSUBMITTED
