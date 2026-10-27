from collections.abc import Callable
from unittest.mock import patch

import pytest
from django.urls import reverse
from journal.models import Journal
from plugins.wjs_submission.models import AccessMode, AccessModeJournal, RevisionStorage
from plugins.wjs_submission.workflow import STEPS, Step, StepState
from submission.models import STAGE_UNDER_REVISION, Article, Licence


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
                func = states[index].step.check_function
                expected = True if func is None else func(journal)
                assert states[index].state == expected


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
    assert step.get_incomplete_step_url(article) == reverse(
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
def test_step_next_step_skip_current(
    journal: Journal,
    install_plugins: Callable,
    article: Article,
    step_number: int,
):
    """
    If an article is submitted, we can calculate the next step URL (including the final step to the status page).

    In case the current step is greater than the last step stored in the article, the greater of the two step number is
    used to calculate the next step URL..

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
    article.current_step = step_number - 1
    with patch.object(step, "check_function", return_value=False):
        url_name = f"wjs_submission_{step_number + 1}" if step_number < 8 else "wjs_submission_0"
        assert step.get_incomplete_step_url(article) == reverse(
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
    assert step.get_incomplete_step_url(None) == reverse(
        url_name,
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
def test_step_state_mapping(
    article: Article,
    install_plugins: Callable,
    step_number: int,
):
    """
    Each step state is marked as available if its step number is less than or equal to the current step number + 1.

    Ie: As the current step is the last step the article has successfully submitted, all steps before it and the
    next one are available.

    :param article: An instance of a submitted article, used to test the mapping of steps to states.
    :type article: Article
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param step_number: An integer representing the step number to be tested.
    :type step_number: int
    :param step_number:
    """
    article.current_step = step_number
    states = Step.get_steps_states(article.journal, article)
    next_granted = False
    for state in states.values():
        if not state.state:
            # Inactive steps are never available.
            assert state.available is False
        elif state.step.step_number <= step_number:
            # Completed active steps are available.
            assert state.available is True
        elif not next_granted:
            # The single next active step (look-ahead) is available.
            assert state.available is True
            next_granted = True
        else:
            # Any active step beyond the next one is blocked.
            assert state.available is False


@pytest.mark.parametrize(
    ("funding_active", "access_mode_active", "active"),
    [
        (True, True, True),
        (False, True, True),
        (True, False, True),
        (False, False, True),
    ],
)
@pytest.mark.django_db
def test_step_7(
    article: Article,
    install_plugins: Callable,
    funding_active: bool,
    access_mode_active: bool,
    active: bool,
):
    """
    Verify conditions for enabling step 7.

    :param article: An instance of a submitted article, used to test the mapping of steps to states.
    :type article: Article
    :param install_plugins: A callable function to set up required plugins for the journal test.
    :type install_plugins: Callable
    :param funding_active: Active funding section.
    :type funding_active: bool
    :param access_mode_active: Active access mode section.
    :type access_mode_active: bool
    :param active: Expected step status.
    :type active: bool
    """
    article.journal.submissionconfiguration.funding = funding_active
    article.journal.submissionconfiguration.save()
    if access_mode_active:
        access_mode = AccessMode.objects.all().first()
        licence = Licence.objects.filter(journal=article.journal).first()
        AccessModeJournal.objects.create(journal=article.journal, licence=licence, access_mode=access_mode)
    else:
        AccessModeJournal.objects.all().delete()
    step = STEPS[7]
    assert step.is_active(journal=article.journal, article=article) == active


@pytest.mark.parametrize(
    ("current_step", "expected_available"),
    [
        # Author still on step 1: step 2 skipped, step 3 is the next reachable step.
        (1, {1: True, 2: False, 3: True, 4: False, 5: False, 6: False, 7: False, 8: False}),
        # Author completed step 3 (current_step jumped 1 -> 3 over the inactive step 2).
        # Only steps 1 and 3 are done and step 4 is the single next step; step 5+ must be blocked.
        # Regression: the previous offset logic double-counted the skipped step 2 and wrongly
        # marked step 5 as available here.
        (3, {1: True, 2: False, 3: True, 4: True, 5: False, 6: False, 7: False, 8: False}),
        # Deeper in the wizard the off-by-one must not reappear either.
        (4, {1: True, 2: False, 3: True, 4: True, 5: True, 6: False, 7: False, 8: False}),
    ],
)
@pytest.mark.django_db
def test_step_state_mapping_skipped_step_no_lookahead_drift(
    article: Article,
    install_plugins: Callable,
    current_step: int,
    expected_available: dict[int, bool],
):
    """
    When an inactive step precedes ``current_step`` availability must not drift by one.

    Scenario: step 2 ("Select Issue") is inactive (no special issue). Since inactive steps are
    skipped without being saved, ``current_step`` jumps over their numbers. Only the completed
    active steps plus the single next active step may be available.
    """
    article.current_step = current_step
    step2 = STEPS[2]
    with patch.object(step2, "check_function", return_value=False):
        states = Step.get_steps_states(article.journal, article)

    # Step 2 is inactive: not rendered and never available.
    assert states[2].state is False
    assert states[2].available is False

    for number, expected in expected_available.items():
        assert states[number].available is expected, (
            f"step {number}: expected available={expected}, got {states[number].available}"
        )


def _start_revision(article: Article, flow_type: str, revision_step: int = 0) -> RevisionStorage:
    """Put an already submitted article (``current_step`` 8) under revision, at the given revision step."""
    article.current_step = 8
    article.stage = STAGE_UNDER_REVISION
    article.save()
    return RevisionStorage.objects.create(article=article, revision_flow_type=flow_type, revision_step=revision_step)


def _available(states: dict[int, StepState]) -> set[int]:
    """Return the numbers of the steps marked as available."""
    return {number for number, state in states.items() if state.available}


@pytest.mark.parametrize(
    ("flow_type", "revision_step", "expected"),
    [
        (RevisionStorage.RevisionFlowType.CONFIRM, 0, {1}),
        (RevisionStorage.RevisionFlowType.CONFIRM, 1, {1, 8}),
        (RevisionStorage.RevisionFlowType.METADATA, 0, {1}),
        (RevisionStorage.RevisionFlowType.METADATA, 1, {1, 4}),
        (RevisionStorage.RevisionFlowType.METADATA, 5, {1, 4, 5, 7}),
        (RevisionStorage.RevisionFlowType.FULL, 0, {1}),
        (RevisionStorage.RevisionFlowType.FULL, 1, {1, 4}),
        (RevisionStorage.RevisionFlowType.FULL, 5, {1, 4, 5, 6}),
        (RevisionStorage.RevisionFlowType.FULL, 7, {1, 4, 5, 6, 7, 8}),
    ],
)
@pytest.mark.django_db
def test_revision_steps_states(
    article: Article,
    install_plugins: Callable,
    flow_type: str,
    revision_step: int,
    expected: set[int],
):
    """
    During a revision a step is available only once the previous active step has been saved.

    Availability follows ``RevisionStorage.revision_step``, not ``article.current_step`` (8 for any submitted article).
    """
    _start_revision(article, flow_type, revision_step)

    states = Step.get_steps_states(article.journal, article)

    available = _available(states)
    assert available == expected, f"{flow_type} revision at step {revision_step}: available steps {available}"


@pytest.mark.django_db
def test_incomplete_step_url_uses_revision_step(article: Article, install_plugins: Callable):
    """After saving a step during a revision, the author is sent after the last saved revision step."""
    _start_revision(article, RevisionStorage.RevisionFlowType.FULL, revision_step=4)

    url = STEPS[1].get_incomplete_step_url(article)

    assert url == reverse("wjs_submission_5", kwargs={"article_id": article.pk}), f"unexpected redirect {url}"


@pytest.mark.django_db
def test_steps_states_without_article_unchanged(journal: Journal, install_plugins: Callable):
    """Without an article (new submission) only the first step is available."""
    states = Step.get_steps_states(journal)

    assert _available(states) == {1}, f"available steps {_available(states)}"


@pytest.mark.django_db
def test_submission_ignores_missing_revision_storage(article: Article, install_plugins: Callable):
    """A first submission (no RevisionStorage) still follows ``article.current_step``."""
    article.current_step = 4
    with patch.object(STEPS[2], "check_function", return_value=False):
        states = Step.get_steps_states(article.journal, article)

    assert _available(states) == {1, 3, 4, 5}, f"available steps {_available(states)}"


@pytest.mark.django_db
def test_last_completed_step_unsaved_article(journal: Journal, install_plugins: Callable):
    """An article not yet saved has no saved step, and no RevisionStorage lookup is attempted for it."""
    last_completed = Step._get_last_completed_step(Article(journal=journal))  # noqa: SLF001

    assert last_completed == 0, f"unexpected last completed step {last_completed}"
