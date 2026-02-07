from copy import copy

from django import forms
from django.utils.translation import gettext_lazy as _
from events import logic as events_logic
from submission.models import Article, Licence

from ..events import SubmissionEvent
from ..models import (
    AccessMode,
    RevisionStorage,
    RevisionSubmissionArticleFunding,
    SubmissionArticleFunding,
)


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
            if field[1] not in kwargs["initial"] or not kwargs["initial"][field[1]]:
                kwargs["initial"][field[1]] = field[0]
            # form data is overwritten with initial values only if calculated values are not customisable by the user
            # in the form UI
            if "data" in kwargs and not self.configuration.user_selectable:
                tmp = copy(kwargs["data"])
                tmp[field[1]] = field[0]
                kwargs["data"] = tmp
        return kwargs

    def _setup_fields(self):
        """
        Configure fields according to access mode configuration.
        """
        self.fields["license"].queryset = Licence.objects.filter(journal=self.journal)
        if self.configuration.user_selectable:
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


class AddFundingForm(forms.ModelForm):
    class Meta:
        model = SubmissionArticleFunding
        fields = ["country", "name", "fundref_id", "funding_id", "funding_statement", "article"]
        labels = {
            "country": "Country of Funding",
        }
        widgets = {
            "article": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        """
        Initialize the instance and its attributes.

        Sets up default and instance-specific initial values for form fields. Provides functionality to support
        both creation (when an article is being assigned funding) and edit modes (when modifying the
        funding information for an article). Additionally, ensures specific fields
        (when information is coming from a typeahead dropdown) are set to readonly when
        appropriate.

        :param args: Positional arguments passed to the parent class.
        :type args: tuple
        :param kwargs: Keyword arguments containing initialization data such as article
                       information, funding details, and other metadata.
        :type kwargs: dict
        """
        self.is_revision = kwargs.pop("is_revision", False)
        self.article = kwargs.pop("article")
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["name"].widget.attrs["readonly"] = True
            self.fields["fundref_id"].widget.attrs["readonly"] = True
            self.fields["country"].widget.attrs["readonly"] = True
        self.data = self.data.copy()
        self.data["article_id"] = self.article.pk
        self.data["article"] = self.article

    def clean_article(self) -> Article:
        """
        Force current article to be returned.

        Avoid tampering attempts.

        :return: Article instance associated with the form.
        :rtype: Article
        """
        return self.article


class RevisionAddFundingForm(AddFundingForm):
    class Meta:
        model = RevisionSubmissionArticleFunding
        fields = ["country", "name", "fundref_id", "funding_id", "funding_statement"]


class RevisionStep7Form(SubmissionStep7Form):
    def __init__(self, *args, **kwargs):
        """
        Initialize a custom form with pre-filled initial data based on revision storage.

        The constructor fetches the associated `RevisionStorage` object for the given `Article` instance
        and initializes specific form fields using data from the `RevisionStorage`.

        :param args: Positional arguments passed to the superclass initializer.
        :type args: tuple
        :param kwargs: Keyword arguments passed to the superclass initializer. It must contain the key
            `instance`, which refers to an `Article` instance.
        :type kwargs: dict
        """
        revision_storage = RevisionStorage.objects.get(article=kwargs["instance"])
        kwargs.setdefault("initial", {})
        for field, value in revision_storage.data.items():
            if field == "confirm_previous_version":
                continue
            kwargs["initial"][field] = value
        super().__init__(*args, **kwargs)
