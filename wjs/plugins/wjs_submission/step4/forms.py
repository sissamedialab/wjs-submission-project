from core import files as core_files
from core.models import Account, Country
from django import forms
from django.utils.translation import gettext_lazy as _
from submission.models import Article, ArticleAuthorOrder

from ..models import ArticleCollaboration, Collaboration


class SubmissionStep4Form(forms.ModelForm):
    country = forms.ModelChoiceField(queryset=Country.objects.all())
    collaboration_relation = forms.ChoiceField(
        choices=ArticleCollaboration.Relations.choices,
        widget=forms.RadioSelect(
            attrs={"class": "form-check-input", "data-name": "collaboration_relation", "data-type": "radio-select"}
        ),
        required=True,
        label=_("This article is written"),
    )

    class Meta:
        model = Article
        fields = ["correspondence_author"]

    def __init__(self, *args, **kwargs):
        """
        Initialize form.

        Correspondence author queryset is set as authors already in ArticleAuthorOrder.
        Accounts without neither institution nor department or last name are marked as disabled and can't be selected.
        Added errors in case metadata is missing from authors.

        :param args: Positional arguments passed to the parent form.
        :param kwargs: Keyword arguments; none mandatory;
        """
        super().__init__(*args, **kwargs)

        if self.instance.correspondence_author:
            self.fields["correspondence_author"].initial = self.instance.correspondence_author
        qs = Account.objects.filter(
            id__in=ArticleAuthorOrder.objects.filter(article=self.instance).values_list("author_id", flat=True)
        )
        self.fields["correspondence_author"].queryset = qs

        self.disabled_accounts = {a.id for a in qs if ((not a.institution and not a.department) or (not a.last_name))}

        if self.instance.correspondence_author.id in self.disabled_accounts:
            if self.instance.correspondence_author == self.instance.owner:
                self.correspondence_author_error = "complete_profile"
            else:
                self.correspondence_author_error = "disabled_account"
        elif not self.instance.correspondence_author.orcid:
            self.correspondence_author_error = "missing_orcid"

        if self.instance.correspondence_author:
            self.fields["correspondence_author"].initial = self.instance.correspondence_author
            self.fields["country"].initial = self.instance.correspondence_author.country

    def save(self, commit: bool = True) -> Account:
        """
        Handle only affiliation_country and article.authors.

        The view manages most data due to heavy HTMX usage.
        """
        instance = super().save()

        instance.submission_data.affiliation_country = self.cleaned_data.get("country")
        instance.submission_data.save()

        instance.authors.clear()
        authors = ArticleAuthorOrder.objects.filter(article=instance).values_list("author", flat=True)

        instance.authors.add(*authors)

        if self.cleaned_data.get("collaboration_relation") == "none":
            ArticleCollaboration.objects.filter(article=instance).delete()

        return instance


class AddAuthorForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["email", "first_name", "middle_name", "last_name", "institution", "country"]

    def __init__(self, *args, **kwargs):
        """
        Initialize the form for adding an author to a specific article.

        Binds the form to the Article identified by `article_id` and
        sets required fields for first name, last name, and email.

        :param args: Positional arguments passed to the parent form.
        :param kwargs: Keyword arguments; must include 'article_id'.
        """
        article_id = kwargs.pop("article_id")
        self.article = Article.objects.get(pk=article_id)
        super().__init__(*args, **kwargs)

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].help_text = _("Required")

    def save(self, commit: bool = True) -> Account:
        """
        Save the author instance and create an ArticleAuthorOrder entry.

        :param commit: Whether to commit the instance to the database.
        :return: The saved Account instance.
        """
        instance = super().save()
        ArticleAuthorOrder.objects.get_or_create(
            article=self.article,
            author=instance,
            defaults={"order": self.article.next_author_sort()},
        )
        return instance


class AddCollaborationForm(forms.ModelForm):
    collaboration_relation = forms.ChoiceField(
        choices=ArticleCollaboration.Relations.choices,
        widget=forms.HiddenInput,
        required=True,
        label="This article is written",
    )
    file = forms.ImageField(
        required=False,
        label="Logo",
        widget=forms.ClearableFileInput(
            attrs={"accept": ".png, .jpg, .jpeg"},
        ),
    )

    class Meta:
        model = Collaboration
        fields = ["name", "institutional_email"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2, "cols": 40}),
            "notes": forms.Textarea(attrs={"rows": 2, "cols": 40}),
        }

    def __init__(self, *args, **kwargs):
        """
        Initialize the form for adding a collaboration to a specific article.

        Binds the form to the Article identified by `article_id`, sets
        the initial collaboration relation, and stores the current user.

        :param args: Positional arguments passed to the parent form.
        :param kwargs: Keyword arguments; must include 'article_id',
                       'collaboration_relation', and 'user'.
        """
        article_id = kwargs.pop("article_id")
        self.article = Article.objects.get(pk=article_id)
        self.collaboration_relation = kwargs.pop("collaboration_relation")
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["collaboration_relation"].initial = self.collaboration_relation
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].help_text = _("Required")

    def save(self, commit: bool = True) -> Account:
        """
        Save the collaboration instance, attach the logo file, and create an ArticleCollaboration entry.

        :param commit: Whether to commit the instance to the database.
        :return: The saved Collaboration instance.
        """
        instance = super().save()

        if self.cleaned_data["file"]:
            file = core_files.save_file_to_article(
                file_to_handle=self.cleaned_data["file"],
                article=self.article,
                owner=self.user,
            )
            instance.logo = file
            instance.save()

        ArticleCollaboration.objects.get_or_create(
            article=self.article,
            collaboration=instance,
            defaults={
                "relation": self.cleaned_data["collaboration_relation"],
                "order": instance.next_collaboration_sort(article=self.article),
            },
        )
        return instance
