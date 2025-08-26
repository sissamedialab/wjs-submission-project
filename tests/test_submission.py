from collections.abc import Callable

import pytest
from core.models import Account
from journal.models import Journal
from plugins.wjs_submission.arxiv import HandleArticleCreation
from plugins.wjs_submission.step1 import SubmissionStep1View
from submission.models import STAGE_UNSUBMITTED


@pytest.mark.django_db
def test_submission_without_arxiv(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    fake_request,
):
    """
    Submission process without an associated ArXiv link creates a bare bone submission.

    This test verifies that a submission can be created, ensuring that all required fields are processed
    and saved correctly, even when optional fields such as title and abstract are empty.

    :param journal: The `Journal` instance associated with the submission.
    :param install_plugins: Callable used to set up plugins or dependencies for testing.
    :param user: The `Account` instance representing the user submitting the article.
    :param fake_request: Mocked request object for simulating a POST HTTP request.
    :raises AssertionError: If any of the assertions in the test fail.
    """
    fake_request.method = "POST"
    fake_request.POST = {
        "copyright_notice": "on",
        "competing_interests": "b",
        "submission_requirements": "c",
        "comments_editor": "d",
    }
    fake_request.user = user
    view_obj = SubmissionStep1View()
    view_obj.kwargs = {}
    view_obj.request = fake_request
    view_obj.object = None

    form = view_obj.get_form()
    assert form.instance.pk is None
    assert form.is_valid()
    article = form.save()
    assert article.pk
    assert article.journal == journal
    assert article.owner == user
    assert article.correspondence_author == user
    assert not article.title
    assert not article.abstract
    assert article.stage == STAGE_UNSUBMITTED
    assert article.current_step == 1
    assert article.competing_interests == "b"
    assert article.submission_requirements
    assert article.copyright_notice
    assert article.comments_editor == "d"


@pytest.mark.django_db
def test_submission_with_arxiv(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    arxiv_metadata: Callable,
    fake_request,
):
    """
    Submission process with an associated ArXiv link creates a populate submission.

    Test the submission process with an associated ArXiv link. This test verifies
    that a submission can be created, ensuring that all required fields are processed
    and saved correctly, even when optional fields such as title and abstract are empty, including the ArXiv data.

    :param journal: The `Journal` instance associated with the submission.
    :param install_plugins: Callable used to set up plugins or dependencies for testing.
    :param user: The `Account` instance representing the user submitting the article.
    :param fake_request: Mocked request object for simulating a POST HTTP request.
    :raises AssertionError: If any of the assertions in the test fail.
    """
    result, __ = arxiv_metadata("2504.10562v1")
    service = HandleArticleCreation(user, result, journal)
    article = service.run()

    fake_request.method = "POST"
    fake_request.POST = {
        "copyright_notice": "on",
        "competing_interests": "b",
        "submission_requirements": "c",
        "comments_editor": "d",
        "arxiv_article_id": article.pk,
    }
    fake_request.user = user
    view_obj = SubmissionStep1View()
    view_obj.kwargs = {}
    view_obj.request = fake_request
    view_obj.object = article

    form = view_obj.get_form()
    assert form.instance.pk is not None
    assert form.is_valid()
    article = form.save()
    assert article.pk
    assert article.journal == journal
    assert article.owner == user
    assert article.correspondence_author == user
    assert article.title == result["title"]
    assert article.abstract == result["abstract"]
    assert article.stage == STAGE_UNSUBMITTED
    assert article.current_step == 1
    assert article.competing_interests == "b"
    assert article.submission_requirements
    assert article.copyright_notice
    assert article.comments_editor == "d"
