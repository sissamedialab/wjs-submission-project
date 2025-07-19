from django import forms
from submission.models import Article


class SubmissionStep1Form(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["competing_interests", "comments_editor"]
