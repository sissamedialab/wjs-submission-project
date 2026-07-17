from django import forms
from django.core.exceptions import ValidationError
from submission.models import Licence

from ..models import ArticleSubmission, Collaboration


class CollaborationMergeForm(forms.Form):
    kept = forms.ModelChoiceField(
        queryset=Collaboration.objects.all(),
        label="Kept collaboration",
        help_text="This collaboration will remain after merging.",
    )
    merged = forms.ModelChoiceField(
        queryset=Collaboration.objects.all(),
        label="Merged collaboration",
        help_text="This collaboration will be deleted after merging.",
    )

    def clean(self):
        """
        Validate that two distinct collaborations are selected.

        :raises ValidationError: If two distinct collaborations are not selected.
        """
        cleaned = super().clean()
        if cleaned.get("kept") == cleaned.get("merged"):
            msg = "You must select two distinct collaborations."
            raise ValidationError(msg)
        return cleaned


class ArticleSubmissionAdminForm(forms.ModelForm):
    """
    Form for ArticleSubmissionAdmin that also handles article license and copyright.

    The ``article_license`` and ``article_rights`` fields are read-only (disabled)
    by default.  They become editable only when the corresponding override flag
    (``license_override`` / ``rights_override``) is checked.  On save, custom
    values are applied to the article only when the flag is set; otherwise the
    model's ``save()`` syncs license and rights from the ``AccessModeJournal``
    configuration.
    """

    # These fields live on the related Article, not on ArticleSubmission.
    # We expose them here so the EO can edit them from the same form.
    article_license = forms.ModelChoiceField(
        queryset=Licence.objects.none(),
        required=False,
        label="License",
        help_text="Read-only unless 'License override' is checked.",
    )
    article_rights = forms.CharField(
        required=False,
        label="Copyright",
        help_text="Read-only unless 'Copyright override' is checked.",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    class Meta:
        model = ArticleSubmission
        fields = ["cover_letter_file", "access_mode", "license_override", "rights_override", "special_request"]

    class Media:
        js = ("js/override_toggle.js",)

    def __init__(self, *args, **kwargs):
        """
        Initialize the form, setting initial values and disabling override-controlled fields.

        When the form is bound (submitted), we check the submitted override flags
        so that fields are enabled/disabled based on the *new* values, not just the
        values stored on the instance.  This allows the EO to toggle the override
        checkbox and submit new values in the same request.
        """
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            article = self.instance.article
            self.fields["article_license"].queryset = Licence.objects.filter(journal=article.journal)
            self.fields["article_license"].initial = article.license
            self.fields["article_rights"].initial = article.rights
            # Determine the effective override flag: use submitted data if available,
            # otherwise fall back to the instance's stored value.
            submitted_license_override = None
            submitted_rights_override = None
            if self.is_bound:
                submitted_license_override = self.data.get("license_override")
                submitted_rights_override = self.data.get("rights_override")
            license_override = (
                submitted_license_override in (True, "True", "on", "1", "true")
                if submitted_license_override is not None
                else self.instance.license_override
            )
            rights_override = (
                submitted_rights_override in (True, "True", "on", "1", "true")
                if submitted_rights_override is not None
                else self.instance.rights_override
            )
            # Disable license/copyright fields when the corresponding override flag
            # is not set.  The EO must check the flag to enable editing.
            if not license_override:
                self.fields["article_license"].disabled = True
            if not rights_override:
                self.fields["article_rights"].disabled = True

    def save(self, commit=True):
        """
        Save the ArticleSubmission and update the related Article's license and rights.

        Custom values from the form are applied to the article only when the
        corresponding override flag is set.  When the flag is not set, the
        model's ``save()`` will sync license and rights from the
        ``AccessModeJournal`` configuration.
        """
        instance = super().save(commit=commit)
        if instance and instance.pk:
            article = instance.article
            # The model's save() may have already updated article.license / article.rights
            # in memory (from AccessModeJournal config).  We only overwrite with the
            # EO's form values when the override flag is set.
            if instance.license_override:
                article.license = self.cleaned_data.get("article_license")
            if instance.rights_override:
                article.rights = self.cleaned_data.get("article_rights", "")
            article.save()
        return instance
