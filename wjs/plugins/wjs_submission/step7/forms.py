from copy import copy

from django import forms
from django.utils.translation import gettext_lazy as _
from events import logic as events_logic
from submission.models import Article, Licence

from ..events import SubmissionEvent
from ..models import AccessMode


class SubmissionStep7Form(forms.ModelForm):
    access_mode = forms.ModelChoiceField(queryset=AccessMode.objects.none(), required=True)
    special_request = forms.CharField(
        label=_("If you require a special copyright/licence, please write them here:"),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    rights = forms.CharField(label=_("Copyright declaration"), required=False)
    license = forms.ModelChoiceField(label=_("Article license"), queryset=Licence.objects.none(), required=False)

    class Meta:
        model = Article
        fields = ["license", "rights"]

    def __init__(self, *args, **kwargs):
        """
        Initialise the ArticleInfo form and assign proper attributes to set required fields.
        """
        self.step = kwargs.pop("step")
        self.journal = kwargs.pop("journal")
        self.configuration = kwargs.pop("configuration")
        kwargs = self._inject_configuration_values(kwargs)
        super().__init__(*args, **kwargs)
        self._setup_fields()

    def _inject_configuration_values(self, kwargs):
        """
        Set initial values for fields based on configuration.

        :param kwargs: Form kwargs
        :return: Updated kwargs
        """
        for field in (
            (self.configuration.license, "license"),
            (self.configuration.copyright_text, "rights"),
            (self.configuration.access_mode, "access_mode"),
        ):
            kwargs["initial"][field[1]] = field[0]
            # form data is overwritten with initial values only if calculated values are not a mere default
            if "data" in kwargs and not self.configuration.is_default:
                tmp = copy(kwargs["data"])
                tmp[field[1]] = field[0]
                kwargs["data"] = tmp
        return kwargs

    def _setup_fields(self):
        """
        Configure fields according to access mode configuration.
        """
        self.fields["license"].queryset = Licence.objects.filter(journal=self.journal)
        if self.configuration.is_default:
            self.fields["access_mode"].queryset = AccessMode.objects.filter(
                parameters__journal=self.journal, user_selectable=True
            )
            self.fields["license"].widget = forms.HiddenInput()
            self.fields["rights"].widget = forms.HiddenInput()
        else:
            self.fields["access_mode"].queryset = AccessMode.objects.filter(
                parameters__journal=self.journal, user_selectable=False
            )
            self.fields["access_mode"].widget = forms.HiddenInput()
            self.fields["license"].widget = forms.HiddenInput()
            self.fields["rights"].widget = forms.HiddenInput()
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].widget.attrs["required"] = True
                self.fields[field].help_text = _("Required")

    def save(self, commit=True):
        """
        Extend the save method to set additional data.

        :param commit: commit changes to database
        :return:
        """
        instance = super().save(commit=commit)
        instance.current_step = max(instance.current_step, self.step)
        instance.save()
        instance.submission_data.access_mode = self.cleaned_data["access_mode"]
        instance.submission_data.special_request = self.cleaned_data["special_request"]
        instance.submission_data.save()
        events_logic.Events.raise_event(
            SubmissionEvent.ON_ACCESS_MODE_SELECTION,
            article=instance,
            submission_data=instance.submission_data,
        )
        return instance
