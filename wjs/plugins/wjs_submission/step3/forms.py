from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from submission.models import Article, KeywordArticle
from utils.forms import KeywordModelForm

from .logic import HandleKeywordSelection


class SubmissionStep3Form(KeywordModelForm):
    state = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Article
        fields = ["state"]

    def __init__(self, *args, **kwargs):
        """
        Initialize the form with the custom form data that arrives from POST request.

        We avoid letting Django handle the form creation because an input like "weight_<keyword_pk>": <weight_value>
        might be complex enough to make a custom form preferable.

        :param args: Positional arguments passed to the parent form.
        :param kwargs: Keyword arguments must include 'form_data'
        """
        self.step = kwargs.pop("step")
        self.form_data = kwargs.pop("form_data")
        super().__init__(*args, **kwargs)
        journal = self.instance.journal
        if (
            journal
            and (
                journal.submissionconfiguration.hierarchical_keywords
                or journal.submissionconfiguration.autocomplete_keywords
            )
            and self.instance.pk
        ):
            self.fields["keywords"].initial = self.instance.keywords.filter(group__isnull=True)
            self.selected_grouped_keywords = {
                ka.keyword_id: ka.weight
                for ka in KeywordArticle.objects.filter(article=self.instance, keyword__group__isnull=False)
            }
        if journal and not journal.submissionconfiguration.autocomplete_keywords:
            self.fields["keywords"] = forms.CharField(required=False, help_text=_("Hit Enter to add a new keyword."))

    def get_logic_instance(self):
        """Instantiate :py:class:`HandleKeywordSelection` class."""
        return HandleKeywordSelection(
            article=self.instance,
            data=self.form_data,
        )

    def save(self, commit=True, *args, **kwargs):
        """
        Save the article and handle the creation of KeywordArticle with the weight selected by the author.

        Also handle the creation of new keywords as free text.

        :raises ValidationError: Raised when the keyword assignation is not successful
        :param commit: A boolean indicating whether to commit the article instance to the
            database or leave it unsaved. Defaults to True.
        :type commit: bool
        :return: The saved article instance
        :rtype: object
        """
        self.instance.current_step = max(self.instance.current_step, self.step)
        # This also takes care of clearing the existing relations
        KeywordModelForm.save(self, commit=commit)
        try:
            service = self.get_logic_instance()
            service.run()
        except ValidationError as e:
            self.add_error(None, e)
            raise
        self.instance.refresh_from_db()
        return self.instance
