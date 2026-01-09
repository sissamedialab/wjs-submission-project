from django import forms
from django.contrib import messages
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from events import logic as events_logic
from submission.models import Article

from ..workflow import WJSSubmissionEvent


class RevisionForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["stage"]

    def __init__(self, request: HttpRequest, *args, **kwargs):
        """Ensure we have a request to pass to the journal-logic function."""
        self.request = request
        super().__init__(*args, **kwargs)

    def save(self, commit=True) -> Article:
        """Let all the operations be performed by event-related functions."""
        events_logic.Events.raise_event(
            WJSSubmissionEvent.ON_REVISION_SUBMISSION_COMPLETED,
            article=self.instance,
            request=self.request,
            commit=commit,
        )
        self.instance.refresh_from_db()
        messages.add_message(
            self.request,
            messages.SUCCESS,
            _('Article "{title}" submitted').format(
                title=self.instance.title,
            ),
        )
        return self.instance
