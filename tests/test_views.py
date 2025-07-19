from collections.abc import Callable
from unittest.mock import patch

import pytest
from django.urls import reverse
from journal.models import Journal
from plugins.wjs_submission.step1 import SubmissionStep1
from plugins.wjs_submission.workflow import STEPS
from submission.models import Article


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
    view_obj = SubmissionStep1()
    view_obj.kwargs = {"article_id": article.pk}
    view_obj.object = article
    view_obj.request = fake_request
    context = view_obj.get_context_data()
    assert context["article"] == article
    assert context["step"] == STEPS.get(1)
    assert context["steps"] == context["step"].get_steps_states(journal)
    for index in STEPS:
        assert context["steps"][index].state is True


@pytest.mark.parametrize("skip", [True, False])
@pytest.mark.django_db
def test_submission_step_1_skip(
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
    step = STEPS.get(1)
    with patch.object(step, "check_function", return_value=not skip):
        view_obj = SubmissionStep1()
        view_obj.kwargs = {"article_id": article.pk}
        view_obj.object = article
        view_obj.request = fake_request
        response = view_obj.get(fake_request, article_id=article.pk)
        if skip:
            assert response.status_code == 302
            assert response.headers.get("Location") == reverse(
                "wjs_submission_2",
                kwargs={"article_id": article.pk},
            )
        else:
            assert response.status_code == 200
