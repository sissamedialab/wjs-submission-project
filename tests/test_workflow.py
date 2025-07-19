from collections.abc import Callable
from unittest.mock import patch

import pytest
from django.urls import reverse
from journal.models import Journal
from plugins.wjs_submission.workflow import STEPS
from submission.models import Article


@pytest.mark.parametrize(
    "step_number,mock_true",  # noqa: PT006
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
def test_step_is_active(
    journal: Journal,
    install_plugins: Callable,
    step_number: int,
    mock_true: bool,
):
    """
    Active state for each step respect the return value of the `check_function` of each step.

    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param step_number: An integer representing the step number to be tested.
    :type step_number: int
    :param mock_true: A boolean value used to mock the return of `check_function` to simulate
        the state of a step.
    :type mock_true: bool
    """
    step = STEPS.get(step_number)
    with patch.object(step, "check_function", return_value=mock_true):
        assert step.is_active(journal) is mock_true


@pytest.mark.parametrize(
    "step_number,mock_true",  # noqa: PT006
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
def test_steps_states(
    journal: Journal,
    install_plugins: Callable,
    step_number: int,
    mock_true: bool,
):
    """
    Dictionary of steps states respect the return value of the `check_function` of each step.

    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param step_number: An integer representing the step number to be tested.
    :type step_number: int
    :param mock_true: A boolean value used to mock the return of `check_function` to simulate
        the state of a step.
    :type mock_true: bool
    """
    step = STEPS.get(step_number)
    with patch.object(step, "check_function", return_value=mock_true):
        states = step.get_steps_states(journal)
        for index in states:
            if index == step_number:
                assert states[index].state is mock_true
            else:
                assert states[index].state


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
def test_step_next_step(
    journal: Journal,
    install_plugins: Callable,
    article: Article,
    step_number: int,
):
    """
    If an article is submitted, we can calculate the next step URL (including the final step to the status page).

    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param step_number: An integer representing the step number to be tested.
    :type step_number: int
    :param article: Submitted article
    :type article: Article
    :param step_number:
    """
    step = STEPS.get(step_number)
    article.current_step = step_number
    url_name = f"wjs_submission_{step_number + 1}" if step_number < 8 else "wjs_submission_0"
    assert step.get_next_step(article) == reverse(
        url_name,
        kwargs={"article_id": article.id},
    )


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
def test_step_next_step_no_article(
    journal: Journal,
    install_plugins: Callable,
    step_number: int,
):
    """
    If an article is submitted, we can calculate the next step URL (including the final step to the status page).

    :param journal: An instance of the Journal object that represents the context for
        evaluating step states.
    :type journal: Journal
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param step_number: An integer representing the step number to be tested.
    :type step_number: int
    :param step_number:
    """
    step = STEPS.get(step_number)
    url_name = "wjs_submission_1"
    assert step.get_next_step(None) == reverse(
        url_name,
    )
