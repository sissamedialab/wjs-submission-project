from django import forms
from django.core.exceptions import ValidationError

from ..models import Collaboration


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
