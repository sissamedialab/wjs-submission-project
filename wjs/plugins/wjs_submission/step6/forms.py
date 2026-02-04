import logging

from core import files
from django import forms
from django.utils.translation import gettext_lazy as _
from django_q.tasks import async_task
from events import logic as event_logic
from submission.models import Article

from .. import settings as submission_settings
from ..models import ArticleSubmission, RevisionStorage
from ..settings import SUBMISSION_FILE_TYPES
from ..workflow import get_feedback_ws_name, get_feedback_ws_url, simulate_yakunin_call

logger = logging.getLogger(__name__)


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
        if instance.submission_data.das == ArticleSubmission.DasDeclaration.URL:
            instance.submission_data.das_url = self.cleaned_data["das_url"]
        else:
            instance.submission_data.das_url = ""
        instance.submission_data.save()  # HELP: drop this. The next "save()" is sufficient (right?)
        instance.submission_data.cas = self.cleaned_data["cas"]
        if instance.submission_data.cas == ArticleSubmission.CasDeclaration.URL:
            instance.submission_data.cas_url = self.cleaned_data["cas_url"]
        else:
            instance.submission_data.cas_url = ""
        instance.submission_data.save()
        return instance


class UploadArticleForm(forms.Form):
    file_type = forms.ChoiceField(
        label=_("File type"),
        choices=(("manuscript", _("Manuscript")), ("data", _("Data/Figure"))),
        required=False,
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
        label=_("Source format"),
        choices=ArticleSubmission.TexEngine.choices,
        required=False,
    )
    tex_master = forms.CharField(
        label=_("TeX Master"),
        help_text=_("Only when more than one TeX file is present"),
        required=False,
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
        self.request = kwargs.pop("request")
        self.new_file = None
        kwargs["prefix"] = self.file_type
        super().__init__(*args, **kwargs)
        if self.file_type != "manuscript" or "text/x-tex" not in self.supported_file_types:
            self.fields["source_format"].required = False
            self.fields["source_format"].widget = forms.HiddenInput()
            self.fields["tex_engine"].widget = forms.HiddenInput()
            self.fields["tex_master"].widget = forms.HiddenInput()
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].widget.attrs["required"] = True
                self.fields[field].help_text = _("Required")

    @property
    def supported_file_types(self):
        """
        Retrieve the supported file types for submissions based on the journal code.

        :return: The list of supported file types for the journal.
        :rtype: list
        """
        return SUBMISSION_FILE_TYPES.get(self.instance.journal.code, SUBMISSION_FILE_TYPES[None])

    def clean_file(self):
        """Validate file mime according to journal and file type form."""
        cleaned_data = super().clean()
        if self.file_type == "manuscript" and cleaned_data["file"].content_type not in self.supported_file_types:
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
        # HELP: param "commit" is not used; is it there for compatibility to different callers?
        # Note that we are not a ModelForm
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
                self.instance.source_files.set([new_file])
                article_id = self.instance.pk
                user_id = self.request.user.pk
                feedback_ws_name = get_feedback_ws_name(article_id, user_id)
                feedback_ws_url = get_feedback_ws_url(self.request, article_id, user_id)
                event_logic.Events.raise_event(
                    event_logic.Events.ON_ARTICLE_FILE_UPLOAD,
                    request=self.request,
                    file_id=new_file,
                    original_filename=new_file.original_filename,
                    file_type="manuscript:async",
                    article=self.instance,
                    feedback_ws_url=feedback_ws_url,
                    feedback_ws_name=feedback_ws_name,
                    is_revision=False,  # we know it, because this form is only used for first submissions
                )
                if submission_settings.SIMULATE_YAKUNIN:
                    async_task(simulate_yakunin_call, feedback_ws_name, task_name="simulate-feedback")

            elif file_type == "data":
                self.instance.data_figure_files.add(new_file)

            elif file_type == "administrative":
                self.instance.submission_data.administrative_files.add(new_file)
                self.instance.submission_data.save()  # HELP: is this needed?

            self.new_file = new_file

        else:
            # Catch programming errors :)
            logger.error(f"Unknown file type {file_type} uploaded for article {self.instance.id}")

        return self.instance


class RevisionUploadArticleForm(UploadArticleForm):
    def save(self) -> Article:
        """
        Save the uploaded files to the revision-storage.

        If a "manuscript" was uploaded, save it as "source" and demand it's processing to others by raising an event.

        A new file is created in the article folder upon execution.

        :return: The Article instance.
        :rtype: Article
        """
        revision_storage = RevisionStorage.objects.get(article=self.instance)
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
                revision_storage.data["source_files"] = new_file.id

                article_id = self.instance.pk
                user_id = self.request.user.pk
                feedback_ws_name = get_feedback_ws_name(article_id, user_id)
                feedback_ws_url = get_feedback_ws_url(self.request, article_id, user_id)
                event_logic.Events.raise_event(
                    event_logic.Events.ON_ARTICLE_FILE_UPLOAD,
                    request=self.request,
                    file_id=new_file,
                    original_filename=new_file.original_filename,
                    file_type="manuscript:async",
                    article=self.instance,
                    feedback_ws_url=feedback_ws_url,
                    feedback_ws_name=feedback_ws_name,
                    is_revision=True,  # this form is only used for revisions
                )
                if submission_settings.SIMULATE_YAKUNIN:
                    async_task(simulate_yakunin_call, feedback_ws_name, task_name="simulate-feedback")

            elif file_type == "data":
                revision_storage.data["data_figure_files"].append(new_file.pk)
                # TODO specs#2330:
                # ...  esm = SupplementaryFile.objects.create(file=new_file)
                # ...  revision_storage.data["supplementary_files"].append(esm.id)

            elif file_type == "administrative":
                revision_storage.data["administrative_files"].append(new_file.pk)

            revision_storage.save()
            self.new_file = new_file

        else:
            # Catch programming errors :)
            logger.error(f"Unknown file type {file_type} uploaded for article {self.instance.id}")

        return self.instance


class RevisionStep6Form(SubmissionStep6Form):
    def __init__(self, *args, **kwargs):
        """
        Initialize a custom form with pre-filled initial data based on revision storage.

        The constructor fetches the associated `RevisionStorage` object for the given `Article` instance
        and initializes specific form fields using data from the `RevisionStorage`.

        The manuscript is _not_ initialized to the previous version, because it should be replaced by the author.

        Instead, data/figure files and supplementary files are initialized to the previous ones, because they are
        generally not changed. The author can modify (add/delete/replace) these files anyway.

        :param args: Positional arguments passed to the superclass initializer.
        :type args: tuple
        :param kwargs: Keyword arguments passed to the superclass initializer. It must contain the key
            `instance`, which refers to an `Article` instance.
        :type kwargs: dict
        """
        revision_storage = RevisionStorage.objects.get(article=kwargs["instance"])
        kwargs.setdefault("initial", {})
        kwargs["initial"]["manuscript"] = revision_storage.data.get("manuscript")
        kwargs["initial"]["data_figure_files"] = revision_storage.data.get("data_figure_files")
        kwargs["initial"]["supplementary_files"] = revision_storage.data.get("supplementary_files")
        kwargs["initial"]["administrative_files"] = revision_storage.data.get("administrative_files")
        super().__init__(*args, **kwargs)

    def save(self, commit: bool = True) -> Article:
        """
        Override save method to store field values in RevisionStorage JSON field.

        For FileFields, saves the file using core.files.save_file_to_article() and stores
        the File object's pk in the JSON data.

        :param commit: A boolean indicating whether to commit (not used in this override).
        :type commit: bool
        :return: The instance without saving.
        :rtype: Article
        """
        revision_storage = RevisionStorage.objects.get(article=self.instance)
        revision_storage.revision_step = max(revision_storage.revision_step, self.step)

        revision_storage.data["das"] = self.cleaned_data["das"]
        if revision_storage.data["das"] == ArticleSubmission.DasDeclaration.URL:
            revision_storage.data["das_url"] = self.cleaned_data["das_url"]
        else:
            revision_storage.data["das_url"] = ""
        revision_storage.data["cas"] = self.cleaned_data["cas"]
        if revision_storage.data["cas"] == ArticleSubmission.CasDeclaration.URL:
            revision_storage.data["cas_url"] = self.cleaned_data["cas_url"]
        else:
            revision_storage.data["cas_url"] = ""
        revision_storage.save()
        return self.instance
