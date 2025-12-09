from core import files
from django import forms
from django.utils.translation import gettext_lazy as _
from submission.models import Article

from ..models import ArticleSubmission
from ..settings import SUBMISSION_FILE_TYPES


class SubmissionStep6Form(forms.ModelForm):
    das = forms.ChoiceField(
        choices=ArticleSubmission.DasDeclaration.choices,
        widget=forms.RadioSelect(attrs={"data-name": "das", "data-type": "radio-select"}),
    )
    das_url = forms.URLField(required=False, label="Please insert URL", help_text=_("Required"))
    cas = forms.ChoiceField(
        choices=ArticleSubmission.CasDeclaration.choices,
        widget=forms.RadioSelect(attrs={"data-name": "das", "data-type": "radio-select"}),
    )
    cas_url = forms.URLField(required=False, label="Please insert URL", help_text=_("Required"))

    class Meta:
        model = Article
        fields = ["current_step"]

    def __init__(self, *args, **kwargs):
        """
        Initialise the ArticleInfo form and assign proper attributes to set required fields.
        """
        self.step = kwargs.pop("step")
        self.journal = kwargs.pop("journal")
        kwargs["initial"]["current_step"] = self.step
        if "data" in kwargs:
            d = kwargs["data"].copy()
            d["current_step"] = self.step
            kwargs["data"] = d
        super().__init__(*args, **kwargs)

    def clean_cas_url(self):
        """Check cas_url field when cas required URL."""
        if self.data.get("cas") == "url" and not self.data.get("cas_url"):
            raise forms.ValidationError(_("Please insert URL"))
        return self.cleaned_data["cas_url"]

    def clean_das_url(self):
        """Check das_url field when cas required URL."""
        if self.data.get("das") == "url" and not self.data.get("das_url"):
            raise forms.ValidationError(_("Please insert URL"))
        return self.cleaned_data["das_url"]

    def save(self, commit=True):
        """
        Save the form instance and update associated submission data with provided cleaned data.

        :param commit: Boolean flag to indicate whether to commit the save operation. Defaults to True.
        :type commit: bool
        :return: The saved model instance.
        :rtype: Any
        :raises AttributeError: Raised when required attributes are not present in the form instance.
        """
        self.instance.current_step = max(self.instance.current_step, self.step)
        instance = super().save(commit=commit)
        instance.submission_data.das = self.cleaned_data["das"]
        instance.submission_data.das_url = self.cleaned_data["das_url"]
        instance.submission_data.cas = self.cleaned_data["cas"]
        instance.submission_data.cas_url = self.cleaned_data["cas_url"]
        instance.submission_data.save()
        return instance


class UploadArticleForm(forms.Form):
    file_type = forms.ChoiceField(
        label=_("File type"), choices=(("manuscript", _("Manuscript")), ("data", _("Data/Figure"))), required=False
    )
    label = forms.CharField(label=_("File label"), widget=forms.TextInput(attrs={"placeholder": "Label"}))
    file = forms.FileField(label=_("Source file"), widget=forms.FileInput())
    source_format = forms.ChoiceField(
        label=_("Source format"),
        choices=ArticleSubmission.ManuscriptSourceFormat.choices,
        required=False,
        help_text=_("Manually set your sources format ( tex or odt ) if the system cannot determine it automatically"),
    )
    tex_engine = forms.ChoiceField(
        label=_("Source format"), choices=ArticleSubmission.TexEngine.choices, required=False
    )
    tex_master = forms.CharField(
        label=_("TeX Master"), help_text=_("Only when more than one TeX file is present"), required=False
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize the class with given parameters and configurations.

        :param args: Positional arguments passed to the superclass.
        :param kwargs: Keyword arguments that configure the instance.
            Expected keys include "file_type" (str), "instance" (Article),
            "user" (User), and optionally "original_file".
        :raises KeyError: If expected keys are missing or incorrectly provided.
        """
        self.file_type = kwargs.pop("file_type")
        self.instance: Article = kwargs.pop("instance")
        self.user = kwargs.pop("user")
        self.new_file = None
        kwargs["prefix"] = self.file_type
        super().__init__(*args, **kwargs)
        if self.file_type != "manuscript":
            self.fields["source_format"].required = False
            self.fields["source_format"].widget = forms.HiddenInput()
            self.fields["tex_engine"].widget = forms.HiddenInput()
            self.fields["tex_master"].widget = forms.HiddenInput()
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].widget.attrs["required"] = True
                self.fields[field].help_text = _("Required")

    def clean_file(self):
        """Validate file mime according to journal and file type form."""
        cleaned_data = super().clean()
        if self.file_type == "manuscript":
            permitted_mime_types = SUBMISSION_FILE_TYPES.get(self.instance.journal.code, SUBMISSION_FILE_TYPES[None])
            if cleaned_data["file"].content_type not in permitted_mime_types:
                raise forms.ValidationError("File type not allowed.")
        return cleaned_data["file"]

    def clean(self):
        """
        Clean the data and include the file type in the cleaned data.

        :return: A dictionary containing cleaned data with an added file type.
        :rtype: dict
        :raises ValidationError: If validation in the parent clean method fails.
        """
        cleaned_data = super().clean()
        cleaned_data["file_type"] = self.file_type
        return cleaned_data

    def save(self, commit: bool = True) -> Article:
        """
        Save the cleaned data into an Article instance.

        Process the uploaded file based on the specified
        file type and associate it with the correct relationship in the article. Handle the replacement
        of existing files if needed, depending on the file type. A new file is created and associated
        with the article upon execution.

        :param commit: Flag indicating whether changes should be persisted immediately. Defaults to True.
        :type commit: bool
        :return: The updated Article instance.
        :rtype: Article
        :raises KeyError: If required fields like "file" or "file_type" are missing in cleaned_data.
        """
        uploaded_file = self.cleaned_data["file"]
        label = self.cleaned_data["label"]
        file_type = self.cleaned_data["file_type"]
        if file_type in ["manuscript", "data", "administrative"]:
            new_file = files.save_file_to_article(
                uploaded_file,
                self.instance,
                self.user,
                label=label,
            )
            if file_type == "manuscript":
                self.instance.manuscript_files.set([new_file])
            elif file_type == "data":
                self.instance.data_figure_files.add(new_file)
            elif file_type == "administrative":
                self.instance.submission_data.administrative_files.add(new_file)
                self.instance.submission_data.save()
            self.new_file = new_file
        return self.instance
