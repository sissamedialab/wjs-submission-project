from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from core.models import Account
from django.urls import reverse
from journal.models import Issue, Journal
from submission.models import Article


class StepState(NamedTuple):
    step: "Step"
    state: bool
    available: bool


@dataclass
class Step:
    """
    Represent the submission step and check their availability.
    """

    step_number: int
    """
    The number of the submission steps
    """

    label: str
    """
    Public label of the step
    """

    step_view_name: str
    """
    The name of the view that manages this step
    """

    icon: str
    """
    Name of the icon to be used in the navigation bar
    """

    check_function: Callable[[Journal, Article, Account], bool] | None = None
    """
    A generic function to check the availability of a single step for an article
    """

    def get_next_step(self, article: Article) -> str:
        """
        Return the url of the next step for the given article.

        :param article: Article instance
        :type article: Article
        :return: URL of the next step
        :rtype: str
        """
        try:
            next_step = max(article.current_step, self.step_number) + 1
            if next_step in STEPS:
                return reverse(
                    f"{STEPS[next_step].step_view_name}",
                    kwargs={"article_id": article.id},
                )
            return reverse(
                "wjs_submission_0",
                kwargs={"article_id": article.id},
            )
        except AttributeError:
            return reverse("wjs_submission_1")

    def is_active(
        self,
        journal: Journal,
        article: Article | None = None,
        user: Account | None = None,
    ) -> bool:
        """
        Calculate if the current step is active for the given journal / article.

        :param journal: Journal instance
        :type journal: Journal
        :param article: Article instance, defaults to None
        :type article: Article, optional
        :param user: User instance, defaults to None
        :type user: Account, optional
        :return: True if the step is active, False otherwise
        :rtype: bool
        """
        if not self.check_function:
            return True
        return self.check_function(journal, article, user)

    @classmethod
    def get_steps_states(
        cls,
        journal: Journal,
        article: Article | None = None,
        user: Account | None = None,
    ) -> dict[int, StepState]:
        """
        Return a dictionary with the active/available steps for the given journal / article.

        :param journal: Journal instance
        :type journal: Journal
        :param article: Article instance, defaults to None
        :type article: Article, optional
        :param user: User instance, defaults to None
        :type user: Account, optional
        :return: Dictionary with the step number as key and the active status as value
        :rtype: dict[int, StepState]
        """
        states = {}
        offset = 1
        for step in STEPS.values():
            active = step.is_active(journal, article, user)
            if not active:
                # Non active states does not count towards the availability
                available = False
                offset += 1
            else:
                available = step.step_number <= article.current_step + offset if article else False
            states[step.step_number] = StepState(
                step=step,
                state=active,
                available=available,
            )
        return states


def step_check_select_issue(
    journal: Journal,
    article: Article | None = None,
    user: Account | None = None,
) -> bool:
    """
    Use Janeway Issue manager to determine if there is any available special issue for the current paper.

    - collection() -> filters all Issues with type="collection" (special issues)
    - by_user() -> returns either issues with no invitees or issues where the user is among the invitees
    - open_for_submission() -> uses date_open and date_close to filter out outdated or future issues
    - current_journal() -> only returns issues for the current journal
    """
    return Issue.objects.collection().by_user(user).open_for_submission().current_journal(journal).exists()


def step_check_keywords(
    journal: Journal,
    article: Article | None = None,
    user: Account | None = None,
) -> bool:
    return True


def step_check_authors(
    journal: Journal,
    article: Article | None = None,
    user: Account | None = None,
) -> bool:
    return True


def step_check_metadata(
    journal: Journal,
    article: Article | None = None,
    user: Account | None = None,
) -> bool:
    return True


def step_check_files(
    journal: Journal,
    article: Article | None = None,
    user: Account | None = None,
) -> bool:
    return True


def step_check_access_funding(
    journal: Journal,
    article: Article | None = None,
    user: Account | None = None,
) -> bool:
    return True


def step_check_review_submit(
    journal: Journal,
    article: Article | None = None,
    user: Account | None = None,
) -> bool:
    return True


STEPS = {
    1: Step(step_number=1, label="Start", step_view_name="wjs_submission_1", check_function=None, icon="bi-clipboard"),
    2: Step(
        step_number=2,
        label="Select Issue",
        step_view_name="wjs_submission_2",
        check_function=step_check_select_issue,
        icon="bi-card-checklist",
    ),
    3: Step(
        step_number=3,
        label="Keywords",
        step_view_name="wjs_submission_3",
        check_function=step_check_keywords,
        icon="bi-key",
    ),
    4: Step(
        step_number=4,
        label="Authors",
        step_view_name="wjs_submission_4",
        check_function=step_check_authors,
        icon="bi-person",
    ),
    5: Step(
        step_number=5,
        label="data",
        step_view_name="wjs_submission_5",
        check_function=step_check_metadata,
        icon="bi-file-earmark-text",
    ),
    6: Step(
        step_number=6,
        label="Files",
        step_view_name="wjs_submission_6",
        check_function=step_check_files,
        icon="bi-files",
    ),
    7: Step(
        step_number=7,
        label="Access & funding",
        step_view_name="wjs_submission_7",
        check_function=step_check_access_funding,
        icon="bi-credit-card",
    ),
    8: Step(
        step_number=8,
        label="Review & submit",
        step_view_name="wjs_submission_8",
        check_function=step_check_review_submit,
        icon="bi-search",
    ),
}
