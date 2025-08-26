from collections.abc import Callable
from unittest.mock import patch

import pytest
from core.models import Account
from django.test import Client
from django.urls import reverse
from journal.models import Journal
from plugins.wjs_submission.step1 import SubmissionStep1View
from plugins.wjs_submission.views import SubmissionLastStepRedirectView
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
    Submittion views are only accessible to authenticated users.

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
