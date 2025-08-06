from core import files as core_files
from django import forms
from django.core.exceptions import ValidationError
from django.forms import HiddenInput
from django.utils.translation import gettext_lazy as _
from submission.models import Article, Field, FieldAnswer

from ..arxiv import HandleArticleCreation
from ..forms import WjsMiniHTMLFormField


class SubmissionStep1Form(forms.ModelForm):
    arxiv_article_id = forms.IntegerField(required=False, widget=HiddenInput())
    arxiv_id = forms.CharField(required=False, widget=HiddenInput())
    comments_editor = WjsMiniHTMLFormField(
        label=_("Cover letter"),
        height="15rem",
        help_text=_("missing help text"),
    )
    competing_interests = WjsMiniHTMLFormField(
        label=_("Competing interests"),
        required=True,
        height="15rem",
        help_text=_(
            "If you have any conflict of interests in the publication of this article please state them here."
        ),
    )
    cover_letter_file = forms.FileField(
        required=False,
        label="Upload file",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.docx,.doc,.odt,.rtf"}),
    )

    class Meta:
        model = Article
        fields = [
            "submission_requirements",
            "copyright_notice",
            "competing_interests",
            "comments_editor",
            "arxiv_article_id",
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
        """
        Validate the 'submission_requirements' field in the cleaned data.

        Ensures that the user has agreed to the required submission requirements before proceeding.

        If the field is not checked or agreed upon, a ValidationError is raised.

        :raises ValidationError: If 'submission_requirements' is not agreed upon.
        :rtype: Any
        :return: The validated value of 'submission_requirements' if the check passes.
        """
        val = self.cleaned_data.get("submission_requirements")
        if not val:
            raise forms.ValidationError(_("You must agree to the submission requirements to proceed."))
        return val

    def clean_copyright_notice(self):
        """
        Clean and validates the copyright notice field.

        Retrieve the value of the `copyright_notice` field from the
        cleaned data dictionary. If the value is None or not provided, a
        `forms.ValidationError` is raised, indicating that the copyright notice
        must be accepted to continue. If the value is valid, it returns the cleaned
        value.

        :raises forms.ValidationError: If the `copyright_notice` field is not provided or is empty.

        :return: The validated and cleaned value of the `copyright_notice` field.
        :rtype: Any
        """
        val = self.cleaned_data.get("copyright_notice")
        if not val:
            raise forms.ValidationError(_("You must accept the copyright notice to proceed."))
        return val

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
        if file:
            allowed_extensions = [".pdf", ".docx", ".doc", ".odt", ".rtf"]
            if not any(file.name.lower().endswith(ext) for ext in allowed_extensions):
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
            HandleArticleCreation(
                user=self.user, form_data=self.cleaned_data, journal=self.journal, article=self.instance
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

        if self.cleaned_data.get("cover_letter_file"):
            file = core_files.save_file_to_article(
                file_to_handle=self.cleaned_data["cover_letter_file"],
                article=self.instance,
                owner=self.user,  # FIXME: is this ALWAYS the case?
            )
            self.instance.submission_data.cover_letter_file = file

        # Set the current step to 1 if it's the first time the article is saved, or keep the current one if we are
        # going back to the step 1 from a further one
        self.instance.current_step = max(self.instance.current_step, 1)

        return super().save(commit=commit)
