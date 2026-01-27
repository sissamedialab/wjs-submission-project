from django import forms
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from events import logic as events_logic
from submission.models import Article

from ..events import SubmissionEvent
from .logic import CompleteSubmission


class RevisionForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["stage"]

    def __init__(self, *args, **kwargs):
        """Ensure we have a request to pass to the journal-logic function."""
        self.step = kwargs.pop("step")
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    def save(self, commit=True) -> Article:
        """Let all the operations be performed by event-related functions."""
        events_logic.Events.raise_event(
            SubmissionEvent.ON_REVISION_SUBMISSION_COMPLETED,
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


class SubmissionStep8Form(forms.ModelForm):
    class Meta:
        model = Article
        fields = ()

    def __init__(self, *args, **kwargs):
        """
        Initialize the form with necessary data.

        :param args: Positional arguments passed to the parent form.
        :param kwargs: Keyword arguments; must include 'journal' and 'user'.
        """
        self.step = kwargs.pop("step")
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        """
        Save the article and complete the submission process by calling janeway's events via custom logic.

        :param commit: A boolean indicating whether to commit the article instance to the
            database or leave it unsaved. Defaults to True.
        :type commit: bool
        :return: The saved article instance
        :rtype: object
        """
        self.instance.current_step = max(self.instance.current_step, self.step)
        article = super().save(commit=commit)
        return CompleteSubmission(article=article, request=self.request).run()
