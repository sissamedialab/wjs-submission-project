import dataclasses

from django.db import transaction
from django.http import HttpRequest
from django.utils.timezone import now
from events import logic as event_logic
from submission.models import STAGE_UNASSIGNED, Article
from utils.logger import get_logger

from ..events import SubmissionEvent

logger = get_logger(__name__)


@dataclasses.dataclass
class CompleteSubmission:
    article: Article
    request: HttpRequest
    first_submission: bool = True

    def assign_projected_issue(self):
        """
        Link the article to the issue selected in step 2 and set it as the article primary issue.

        The link cannot be created in step 2 because adding the article to Issue.articles triggers Janeway's
        "issue_articles_change" signal, which creates an ArticleOrdering: its section is not nullable, and the
        article section is only chosen in step 5.

        The article is added from the article side (article.issues.add()) so that the signal works on this very
        instance and our copy of the article does not go stale.
        """
        issue = self.article.projected_issue
        if not issue:
            return
        if not self.article.section:
            logger.warning(
                f"Cannot assign article {self.article.pk} to issue {issue.pk}: the article has no section.",
            )
            return
        if self.article.primary_issue != issue:
            self.article.primary_issue = issue
            self.article.save()
        if not self.article.issues.filter(pk=issue.pk).exists():
            # Also creates the ArticleOrdering / SectionOrdering through "issue_articles_change"
            self.article.issues.add(issue)

    def run(self):
        """
        Execute the article submission process.

        Update its state, saving the changes, and triggering appropriate events to signal the workflow's progress.

        Managed signals:
        - ON_WORKFLOW_ELEMENT_COMPLETE: On article submission only
        - ON_ARTICLE_SUBMITTED: On article submission only
        - ON_REVISION_SUBMISSION_COMPLETED: On revision only
        - ON_ACCESS_MODE_SELECTION: Always

        :raises: RuntimeError if the article submission or workflow updates fail
        :return: Updated article instance after submission
        :rtype: Article
        """
        with transaction.atomic():
            self.assign_projected_issue()
            if self.first_submission:
                self.article.date_submitted = now()
                self.article.stage = STAGE_UNASSIGNED
                self.article.save()
                event_logic.Events.raise_event(
                    event_logic.Events.ON_WORKFLOW_ELEMENT_COMPLETE,
                    handshake_url="submit_review",
                    request=self.request,
                    article=self.article,
                    switch_stage=False,
                )
                event_logic.Events.raise_event(
                    event_logic.Events.ON_ARTICLE_SUBMITTED,
                    task_object=self.article,
                    article=self.article,
                    request=self.request,
                )
            else:
                event_logic.Events.raise_event(
                    SubmissionEvent.ON_REVISION_SUBMISSION_COMPLETED,
                    article=self.article,
                    request=self.request,
                    commit=True,
                )
            event_logic.Events.raise_event(
                SubmissionEvent.ON_ACCESS_MODE_SELECTION,
                article=self.article,
                submission_data=self.article.submission_data,
            )
            self.article.refresh_from_db()
            return self.article
