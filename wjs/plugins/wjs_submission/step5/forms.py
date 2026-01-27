from django import forms
from django.utils.translation import gettext_lazy as _
from submission.forms import ArticleInfo
from submission.models import KeywordArticle

from ..fields import WjsSimpleBleach
from ..settings_helpers import get_article_language_choices


class SubmissionStep5Form(ArticleInfo):
    title = WjsSimpleBleach(
        label=_("Title"),
        max_length=255,
        help_text=_("Required"),
        widget=forms.TextInput(attrs={"placeholder": _("Title")}),
    )

    def __init__(self, *args, **kwargs):
        """
        Initialise the ArticleInfo form and assign proper attributes to set required fields.
        """
        self.step = kwargs.pop("step")
        super().__init__(*args, **kwargs)
        if "language" in self.fields:
            self.fields["language"].required = True
            self.fields["language"].choices = get_article_language_choices(self.instance.journal)
        if "section" in self.fields:
            self.fields["section"].label = _("Article type")
            self.fields["section"].required = True

        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].widget.attrs["required"] = True
                self.fields[field].help_text = _("Required")

    def save(self, commit=True, request=None):
        """
        Set article current step to the form step.
        """
        # Workaround to store keywords after form save because utils.forms.KeywordModelForm.save clears the existing
        # keywords. We must use utils.forms.KeywordModelForm (through ArticleInfo) because we need the logic to
        # handle optional fields and this workaround is slightly better than reimplementing the optional fields logic.
        current_keywords = list(KeywordArticle.objects.filter(article=self.instance))
        self.instance.current_step = max(self.instance.current_step, self.step)
        super().save(commit=commit, request=request)
        self.instance.refresh_from_db()
        for keyword in current_keywords:
            KeywordArticle.objects.create(
                article=self.instance, keyword=keyword.keyword, order=keyword.order, weight=keyword.weight
            )
        return self.instance
