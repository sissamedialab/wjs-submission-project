import contextlib

from core import files as core_files
from core.models import File
from django import forms
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from events import logic as events_logic
from plugins.wjs_submission.workflow import is_revision_confirm, is_revision_full
from submission.models import Article, Field, FieldAnswer
from utils.setting_handler import get_setting

from .. import settings
from ..arxiv import HandleArticleCreation
from ..fields import CoreFileWrapper, WjsMiniHTMLFormField
from ..models import ArticleSubmission, RevisionStorage


class SubmissionStep1Form(forms.ModelForm):
    arxiv_article_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    arxiv_id = forms.CharField(
        label=_("arXiv ID"),
        widget=forms.TextInput(attrs={"placeholder": "", "aria-label": _("Enter archive ID")}),
        required=False,
    )
    comments_editor = WjsMiniHTMLFormField(
        label=_("Cover letter"),
        height="15rem",
        help_text=_("missing help text"),
        required=False,
    )
    competing_interests = WjsMiniHTMLFormField(
        label=_("Competing interests"),
        height="15rem",
        required=False,
    )
    cover_letter_file = forms.FileField(
        label="Upload file",
        # FIXME: "accept" should match ArticleSubmission.cover_letter_file_allowed_extension
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.docx,.doc,.odt,.rtf"}),
        required=False,
    )

    class Meta:
        model = Article
        fields = [
            "submission_requirements",
            "copyright_notice",
            "competing_interests",
            "comments_editor",
            "arxiv_article_id",
            "arxiv_id",
            "cover_letter_file",
        ]

    def __init__(self, *args, **kwargs):
        """
        Handle form initialization logic for submission-related fields in a journal platform.

        Dynamically adjusts form fields based on journal submission configurations
        and additional field requirements specific to the journal. It ensures that fields like
        copyright notice, submission requirements, competing interests, and editor comments are
        conditionally added or modified based on the journal's configuration. Additional fields
        are also incorporated dynamically if defined in the associated journal's field structure.

        :param args: Positional arguments for the superclass initializer.
        :type args: tuple
        :param kwargs: Keyword arguments for the superclass initializer, with specific
            keys such as 'journal' for the journal configuration and 'user' for the current user
            context.
        :type kwargs: dict
        """
        self.step = kwargs.pop("step")
        self.journal = kwargs.pop("journal")
        self.user = kwargs.pop("user")
        self.request = kwargs.pop("request")
        self._additional_fields = Field.objects.filter(journal=self.journal, display=True).order_by("order")
        try:
            # As cover_letter_file is a Janeway core File, we can't just pass it to the form FileField, we must wrap it
            # in something which "resembles" a model FileField instance (ie: a File + a URL).
            # The value is used only for display purposes, because the value is changed only when a new file is
            # uploaded so it should be safe to mock with lookalike classes instead of the real ones.
            cover_letter_file = kwargs.get("instance").submission_data.cover_letter_file
            if cover_letter_file:
                django_file = CoreFileWrapper(cover_letter_file)
                kwargs["initial"].update({"cover_letter_file": django_file})

        except AttributeError:
            pass
        super().__init__(*args, **kwargs)

        competing_interest_instructions_text = mark_safe(  # noqa: S308
            get_setting(
                "wjs_submission",
                "competing_interest_instructions_text",
                self.journal,
            ).processed_value
        )
        self.fields["competing_interests"].help_text = competing_interest_instructions_text
        copyright_label = mark_safe(  # noqa S308
            get_setting(
                "general",
                "copyright_notice",
                self.journal,
            ).processed_value
        )
        self.fields["copyright_notice"].label = copyright_label
        if self.journal.submissionconfiguration.copyright_notice:
            self.fields["copyright_notice"].required = True
        else:
            self.fields.pop("copyright_notice")

        self.fields["submission_requirements"].label = _(
            "I confirm that the above points have been taken into account.",
        )
        if self.journal.submissionconfiguration.submission_check:
            self.fields["submission_requirements"].required = True

        # widget.attrs["required"] must be set on textarea because it's not an attribute supported by default
        # on texarea fields in Django, setting on widget will make it render in the HTML and picked up by the js
        # validation
        if self.journal.submissionconfiguration.competing_interests:
            self.fields["competing_interests"].required = True
            # Using a custom attribute to not trigger bootstrap validation as we use custom logic which checks tinymce
            self.fields["competing_interests"].widget.attrs["js_required"] = True

        if (
            self.journal.submissionconfiguration.comments_to_the_editor
            or is_revision_full(self.instance)
            or is_revision_confirm(self.instance)
        ):
            # Using a custom attribute to not trigger bootstrap validation as we use custom logic which checks tinymce
            self.fields["comments_editor"].widget.attrs["js_required"] = True
            self.fields["comments_editor"].widget.attrs["alternate_field"] = "cover_letter_file"

        arxiv_field_status = get_setting("wjs_submission", "arxiv_field_status", self.journal).processed_value
        if arxiv_field_status == "disabled":
            self.fields.pop("arxiv_article_id")
            self.fields.pop("arxiv_id")
        elif arxiv_field_status == "required":
            self.fields["arxiv_id"].required = True
            self.fields["arxiv_id"].widget.attrs["force_required"] = True
            self.fields["arxiv_article_id"].required = True

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
                if element.required:
                    if self.fields[element.name].help_text:
                        self.fields[
                            element.name
                        ].help_text = f"{_('Required')} - {self.fields[element.name].help_text}"
                    else:
                        self.fields[element.name].help_text = _("Required")

                if self.instance:
                    try:
                        check_for_answer = FieldAnswer.objects.get(field=element, article=self.instance)
                        self.fields[element.name].initial = check_for_answer.answer
                    except FieldAnswer.DoesNotExist:
                        pass

    def clean(self):
        """
        Clean the form data and performs validation for additional fields.

        Extend the standard form clean method to validate
        additional fields that are dynamically added to the form. If any
        of the additional fields marked as required do not have a value
        in `cleaned_data`, an error is added to the respective field.

        :return: A dictionary containing the cleaned form data after
            validation, with possible errors added for invalid or missing
            required fields.
        :rtype: dict
        """
        cleaned_data = super().clean()

        if self.journal.submissionconfiguration.comments_to_the_editor:
            cover_letter_file = self.cleaned_data.get("cover_letter_file")
            comments_editor = self.cleaned_data.get("comments_editor")

            if not cover_letter_file and not comments_editor:
                self.add_error(
                    "comments_editor",
                    _("You must enter a cover letter or upload a file to proceed."),
                )
                self.add_error(
                    "cover_letter_file",
                    _("You must enter a cover letter or upload a file to proceed."),
                )

        for element in self._additional_fields:
            name = element.name
            val = cleaned_data.get(name)
            if element.required and not val:
                self.add_error(
                    name,
                    _("This field (“%(label)s”) is required.") % {"label": element.name},
                )

        return cleaned_data

    def clean_cover_letter_file(self):
        """
        Validate the uploaded file in the 'cover_letter_file' field.

        Checks whether the uploaded file has an allowed extension. Supported extensions
        include: .pdf, .docx, .doc, .odt, and .rtf. If the file is provided but does not match
        any of the allowed formats, a `forms.ValidationError` is raised.

        This validation ensures that authors only upload cover letters in commonly accepted
        document formats compatible with editorial workflows.

        :raises forms.ValidationError: If the uploaded file has an unsupported extension.

        :return: The validated file object if it exists and passes the extension check.
        :rtype: UploadedFile | None
        """
        file = self.cleaned_data.get("cover_letter_file")
        if file and not any(
            file.name.lower().endswith(ext) for ext in ArticleSubmission.cover_letter_file_allowed_extension
        ):
            raise forms.ValidationError("File extension not allowed.")
        return file

    def save(self, commit=True):
        """
        Save the form instance by handling the creation of an article object using provided data.

        Additional fields are processed and saved alongside the article instance.

        If commit is True, the resulting article instance is persisted to the database.
        Instance is returned after completion, allowing further usage.

        :raises ValidationError: Raised when the article creation fails validation.

        :param commit: A boolean indicating whether to commit the article instance to the
            database or leave it unsaved. Defaults to True.
        :type commit: bool
        :return: The saved or unsaved article instance depending on the value of the `commit`
            flag.
        :rtype: object
        """
        try:
            self.instance = HandleArticleCreation(
                user=self.user,
                form_data=self.cleaned_data,
                journal=self.journal,
                article=self.instance,
            ).run()
        except ValidationError as e:
            self.add_error(None, e)
            raise

        for field in self._additional_fields:
            answer = self.cleaned_data.get(field.name)
            if answer:
                FieldAnswer.objects.update_or_create(
                    article=self.instance,
                    field=field,
                    defaults={"answer": answer},
                )
            # Set dependent value on submission_data
            if field.name == settings.USE_OF_AI_FIELD_LABEL:
                self.instance.submission_data.use_of_ai_flag = bool(answer) if answer else False
                self.instance.submission_data.save()

        if self.cleaned_data.get("cover_letter_file"):
            file = core_files.save_file_to_article(
                file_to_handle=self.cleaned_data["cover_letter_file"],
                article=self.instance,
                owner=self.user,  # FIXME: change owner when changing correspondence author
                label="Cover letter",  # NB: fixed label: no translation!
            )
            file.privacy = "owner"
            file.save()
            self.instance.submission_data.cover_letter_file = file
            self.instance.submission_data.save()
        elif self.cleaned_data.get("cover_letter_file") is False:
            # False means that we should clear the existing file
            if self.instance.submission_data.cover_letter_file:
                self.instance.submission_data.cover_letter_file.delete()
            self.instance.submission_data.cover_letter_file = None
            self.instance.submission_data.save()

        # Set the current step to 1 if it's the first time the article is saved, or keep the current one if we are
        # going back to the step 1 from a further one
        self.instance.current_step = max(self.instance.current_step, self.step)

        self.trigger_submissionstart_event()

        return super().save(commit=commit)

    def trigger_submissionstart_event(self):
        """Raise Janeway's ON_ARTICLE_SUBMISSION_START event on initial submission step to trigger further actions."""
        events_logic.Events.raise_event(
            events_logic.Events.ON_ARTICLE_SUBMISSION_START,
            request=self.request,
            article=self.instance,
        )


class RevisionConfirmForm(SubmissionStep1Form):
    """
    Form that lets the author Confirm-Previous-Version.

    We allow the author to maintain the previous version files, but require an explanation (the cover letter).

    All data is kept in the temporary storage RevisionStorage.
    """

    def __init__(self, *args, **kwargs):
        """
        Handle differences in form initialization logic for revisions.

        - use RevisionStorage to bind the form with saved data
        - set some fields as read-only
        - change the submission-requirements list to the revision-requirements list
        """
        revision_storage = RevisionStorage.objects.get(article=kwargs["instance"])
        kwargs.setdefault("initial", {})
        for field, value in revision_storage.data.items():
            if field == "confirm_previous_version":
                continue
            kwargs["initial"][field] = value

        super().__init__(*args, **kwargs)

        if cover_letter_file_id := revision_storage.data.get("cover_letter_file"):
            django_file = CoreFileWrapper(File.objects.get(id=cover_letter_file_id))
            self.initial.update({"cover_letter_file": django_file})
        else:
            self.initial.update({"cover_letter_file": None})

        if not get_setting("general", "revision_checklist", self.journal).processed_value:
            self.fields["submission_requirements"].widget = forms.HiddenInput()
            self.fields["submission_requirements"].required = False

        # Make arxiv_id field non-editable
        # (the visible/non-visible configuration is managed by our parent class)
        if "arxiv_id" in self.fields:
            self.fields["arxiv_id"].disabled = True
            self.fields["arxiv_id"].widget.attrs["readonly"] = True

    def clean_submission_requirements(self):
        """
        Force value of submission_requirements depending if the revision checklist is enabled.

        :return: Processed submission requirements or a boolean indicating
                 checklist validation bypass status
        :rtype: Union[bool, Any]
        :raises KeyError: If 'submission_requirements' is not present in
                          cleaned_data
        """
        if not get_setting("general", "revision_checklist", self.journal).processed_value:
            return True
        return self.cleaned_data["submission_requirements"]

    def save(self, commit: bool = True):
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

        for field_name, field_value in self.cleaned_data.items():
            field = self.fields.get(field_name)

            if isinstance(field, forms.FileField):
                if field_name == "cover_letter_file":
                    if field_value is None:
                        pass
                    elif field_value is False:
                        # "False" here means that we should clear the existing file
                        # We want to ignore non existing file (which means the user have some some back-and-fort
                        # or messed with parallels tabs
                        with contextlib.suppress(File.DoesNotExist):
                            File.objects.get(id=revision_storage.data[field_name]).delete()
                        revision_storage.data.pop(field_name)
                    else:
                        # Delete existing (draft) file if it exists
                        if old_file_id := revision_storage.data.get(field_name):
                            # We want to ignore non existing file (which means the user have some some back-and-fort
                            # or messed with parallels tabs
                            with contextlib.suppress(File.DoesNotExist):
                                File.objects.get(id=old_file_id).delete()

                        # Save the file and store its pk
                        saved_file = core_files.save_file_to_article(
                            file_to_handle=field_value,
                            article=self.instance,
                            owner=self.user,
                            label="Cover letter",  # NB: fixed label: no translation!
                        )
                        revision_storage.data[field_name] = saved_file.pk
                else:
                    raise ValueError(f"Unmanaged file field {field_name}")
            else:
                # Store the value directly (will be JSON-serializable)
                revision_storage.data[field_name] = field_value

        # Store additional submission fields.
        # They will be "saved" when the revision submission is complete.
        for field in self._additional_fields:
            if answer := self.cleaned_data.get(field.name):
                revision_storage.data[field.name] = answer

        revision_storage.save()

        return self.instance


class RevisionMetadataForm(RevisionConfirmForm):
    """
    Form that lets the author perform changes to metadata only.

    All data is kept in the temporary storage RevisionStorage.
    """

    def __init__(self, *args, **kwargs):
        """Disable the cover letter (section 4)."""
        super().__init__(*args, **kwargs)
        del self.fields["comments_editor"]
        del self.fields["cover_letter_file"]

    def clean(self):
        """
        No cover letter.

        Revisions of this type do not require a cover letter (comments_editor/ cover_letter_file),
        while our parent's clean() method expects it.

        Here we copy RevisionConfirmForm.clean(), omitting the cover-letter part.

        :return: A dictionary containing the cleaned form data after
            validation, with possible errors added for invalid or missing
            required fields.
        :rtype: dict
        """
        cleaned_data = ModelForm.clean(self)

        for element in self._additional_fields:
            name = element.name
            val = cleaned_data.get(name)
            if element.required and not val:
                self.add_error(
                    name,
                    _("This field (“%(label)s”) is required.") % {"label": element.name},
                )

        return cleaned_data


class RevisionFullForm(RevisionConfirmForm):
    """
    Form that lets the author perform a full (normal) revision.

    All data is kept in the temporary storage RevisionStorage.
    """
