from django import forms
from django.core.exceptions import ValidationError
from django.forms import HiddenInput
from django.utils.translation import gettext_lazy as _
from submission.models import Article, Field, FieldAnswer

from ..arxiv import HandleArticleCreation
from ..forms import WjsMiniHTMLFormField


class SubmissionStep1Form(forms.ModelForm):
    arxiv_article_id = forms.IntegerField(required=False, widget=HiddenInput())

    class Meta:
        model = Article
        fields = [
            "submission_requirements",
            "copyright_notice",
            "competing_interests",
            "comments_editor",
        ]

    def __init__(self, *args, **kwargs):
        self.journal = kwargs.pop("journal")
        self.user = kwargs.pop("user")
        self._additional_fields = Field.objects.filter(journal=self.journal).order_by("order")
        super().__init__(*args, **kwargs)

        if not self.journal.submissionconfiguration.copyright_notice:
            self.fields.pop("copyright_notice")
        else:
            self.fields["copyright_notice"].required = True

        if not self.journal.submissionconfiguration.submission_check:
            self.fields.pop("submission_requirements")
        else:
            self.fields["submission_requirements"].required = True

        self.fields["competing_interests"] = WjsMiniHTMLFormField(
            label=_("Competing interests"),
            required=True,
            height="15rem",
            help_text=_(
                "If you have any conflict of interests in the publication of this article please state them here."
            ),
        )
        self.fields["comments_editor"] = WjsMiniHTMLFormField(
            label=_("Cover letter"),
            height="15rem",
            help_text=_("missing help text"),  # FIXME: Generally, we are missing form help texts
        )
        # the following code is copied from submission.forms.ArticleInfo
        if self._additional_fields:
            for element in self._additional_fields:
                # Add any missing element kinds if necessary
                if element.kind == "text":
                    self.fields[element.name] = forms.CharField(
                        widget=forms.TextInput(attrs={"div_class": element.width}),
                        required=element.required,
                    )
                elif element.kind == "textarea":
                    self.fields[element.name] = WjsMiniHTMLFormField(
                        required=element.required,
                    )
                elif element.kind == "check":
                    self.fields[element.name] = forms.BooleanField(
                        widget=forms.CheckboxInput(attrs={"is_checkbox": True}),
                        required=element.required,
                    )

                self.fields[element.name].help_text = element.help_text
                self.fields[element.name].label = element.name

                if self.instance:
                    try:
                        check_for_answer = FieldAnswer.objects.get(field=element, article=self.instance)
                        self.fields[element.name].initial = check_for_answer.answer
                    except FieldAnswer.DoesNotExist:
                        pass

    def clean(self):
        cleaned_data = super().clean()

        for element in self._additional_fields:
            name = element.name
            val = cleaned_data.get(name)
            if element.required and not val:
                self.add_error(
                    name,
                    _("This field (“%(label)s”) is required.") % {"label": element.name},
                )

        return cleaned_data

    def clean_submission_requirements(self):
        val = self.cleaned_data.get("submission_requirements")
        if not val:
            raise forms.ValidationError(_("You must agree to the submission requirements to proceed."))
        return val

    def clean_copyright_notice(self):
        val = self.cleaned_data.get("copyright_notice")
        if not val:
            raise forms.ValidationError(_("You must accept the copyright notice to proceed."))
        return val

    def save(self, commit=True):
        arxiv_id = self.cleaned_data.get("arxiv_article_id")
        try:
            article = HandleArticleCreation(
                user=self.user,
                form_data=self.cleaned_data,
                journal=self.journal,
                article_id=arxiv_id,
            ).run()
        except ValidationError as e:
            self.add_error(None, e)
            raise

        for field in self._additional_fields:
            answer = self.cleaned_data.get(field.name)
            if answer:
                FieldAnswer.objects.update_or_create(
                    article=article,
                    field=field,
                    defaults={"answer": answer},
                )
        article.submission_requirements = self.cleaned_data.get("submission_requirements")
        article.copyright_notice = self.cleaned_data.get("copyright_notice")
        article.competing_interests = self.cleaned_data.get("competing_interests")
        article.comments_editor = self.cleaned_data.get("comments_editor")

        if commit:
            article.save()

        for field in self._additional_fields:
            answer = self.cleaned_data.get(field.name)
            if answer is not None:
                FieldAnswer.objects.update_or_create(
                    article=article,
                    field=field,
                    defaults={"answer": answer},
                )

        self.instance = article
        return self.instance
