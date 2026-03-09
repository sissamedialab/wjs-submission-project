from django import forms
from django.utils.translation import gettext_lazy as _
from journal.models import ArticleOrdering, Issue
from submission.models import Article

from ..templatetags.submission_tags import display_title


# FIXME: this code was copied as is from WJS
class IssueModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):  # noqa: PLR6301
        """
        Return a value as it should appear when rendered in a template.
        """
        if obj is None:
            return None
        return display_title(obj)

    def clean(self, value):
        """
        Workaround to keep the field "Required" for frontend logic but accept the empty option as a valid input.

        This ensures that when the empty option (e.g., "First standard issue available") is selected,
        the field does not raise a validation error and instead stores `None` in the model.

        :param value: The raw value submitted for the projected_issue field. Could be a primary key (str/int) or
        an empty string.
        :return: The corresponding Issue instance if selected, or None if the empty option is chosen.
        """
        if value in self.empty_values:
            return None
        return super().clean(value)


class SubmissionStep2Form(forms.ModelForm):
    projected_issue = IssueModelChoiceField(
        queryset=None,
        required=True,
        blank=True,
        empty_label="Standard issue",
        widget=forms.RadioSelect(),
        label=_("Issue"),
    )

    class Meta:
        model = Article
        fields = ("projected_issue",)

    def __init__(self, *args, **kwargs):
        """
        Initialize the form with journal and user context.

        Dynamically sets the queryset and labels for the projected_issue field.
        The queryset includes only open issues available to the given user and journal,
        and each option is rendered with its issue title.

        :param args: Positional arguments passed to the parent form.
        :param kwargs: Keyword arguments; must include 'journal' and 'user'.
        """
        self.step = kwargs.pop("step")
        self.journal = kwargs.pop("journal")
        self.user = kwargs.pop("user")
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields["projected_issue"].queryset = (
            Issue.objects.collection().by_user(self.user).open_for_submission().current_journal(self.journal)
        )
        self.fields["projected_issue"].label_from_instance = lambda obj: f"{obj.issue_title}"

    def save(self, commit=True):
        """
        Save the article and update its projected issue and step.

        This method assigns the selected projected issue to the article, clears related links
        if no issue is selected, and advances the current step.

        :raises ValidationError: Raised when the article creation fails validation.
        :param commit: A boolean indicating whether to commit the article instance to the
            database or leave it unsaved. Defaults to True.
        :type commit: bool
        :return: The saved article instance
        :rtype: object
        """
        self.instance.current_step = max(self.instance.current_step, self.step)
        obj = super().save(commit=commit)
        # Reset all links to any previously selected issue and clear the article primary issue
        # Note that in the submit_info view, after this form is saved, handle_assign_issue() is called,
        # which adds the article to it's (projected-)Issue.articles list,
        # which, in turn, triggers a signal (see below) that sets the ordering and the article.primary_issue.
        # The following line also activates the signal "issue_articles_change"
        Issue.articles.through.objects.filter(article=obj).delete()
        ArticleOrdering.objects.filter(article=obj).delete()
        obj.primary_issue = None
        if self.cleaned_data["projected_issue"]:
            obj.primary_issue = self.cleaned_data["projected_issue"]
        return obj
