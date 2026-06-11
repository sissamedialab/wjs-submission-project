import dataclasses

from django.db import transaction
from django.http import HttpRequest
from django.utils.timezone import now
from events import logic as event_logic
from submission.models import STAGE_UNASSIGNED, Article

from ..events import SubmissionEvent


@dataclasses.dataclass
class CompleteSubmission:
    article: Article
    request: HttpRequest
    first_submission: bool = True

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
            if self.first_submission:
                self.article.date_submitted = now()
                self.article.stage = STAGE_UNASSIGNED
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
            self.article.save()
            self.article.refresh_from_db()
            return self.article
