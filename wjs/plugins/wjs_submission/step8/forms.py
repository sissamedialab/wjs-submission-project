from django import forms
from submission.models import Article

from .logic import CompleteSubmission


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
        Save the article and complete the submission process by calling janeway's events.

        :param commit: A boolean indicating whether to commit the article instance to the
            database or leave it unsaved. Defaults to True.
        :type commit: bool
        :return: The saved article instance
        :rtype: object
        """
        self.instance.current_step = max(self.instance.current_step, self.step)
        article = super().save(commit=commit)
        return CompleteSubmission(article=article, request=self.request).run()
