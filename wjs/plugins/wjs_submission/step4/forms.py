from core import files as core_files
from core.models import Account, Country
from django import forms
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from submission.models import Article, ArticleAuthorOrder

from ..account_validation import (
    ProfileCompletionStatus,
    is_user_eligible_for_correspondence_author,
    verify_profile_completion,
)
from ..fields import WjsMiniHTMLFormField
from ..models import (
    ArticleCollaboration,
    Collaboration,
    CollaborationRelation,
    RevisionArticleAuthorOrder,
    RevisionArticleCollaboration,
    RevisionStorage,
)


class SubmissionStep4Form(forms.ModelForm):
    country = forms.ModelChoiceField(queryset=Country.objects.all())
    collaboration_relation = forms.ChoiceField(
        choices=CollaborationRelation.choices,
        widget=forms.RadioSelect(
            attrs={"class": "form-check-input", "data-name": "collaboration_relation", "data-type": "radio-select"}
        ),
        required=True,
        label=_("This article is written"),
    )
    statuses = ProfileCompletionStatus

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
        self.step = kwargs.pop("step", None)
        super().__init__(*args, **kwargs)

        authors_list = self._get_correspondence_author_list(self.instance)
        self.fields["correspondence_author"].queryset = authors_list

        self.disabled_accounts = self._get_disabled_accounts(authors_list)
        # The following error can be used by the view's template in order to
        # indicate required/desirable actions to the operator:
        self.correspondence_author_error = verify_profile_completion(
            journal=self.instance.journal,
            disabled_users=self.disabled_accounts,
            user=self.instance.correspondence_author,
            is_owner=self.instance.correspondence_author == self.instance.owner,
        )

        if self.instance.correspondence_author:
            self.fields["correspondence_author"].initial = self.instance.correspondence_author
            self.fields["country"].initial = self.instance.correspondence_author.country

        self.fields["collaboration_relation"].initial = (
            ArticleCollaboration.objects.filter(article=self.instance).values_list("relation", flat=True).first()
        ) or CollaborationRelation.NONE

    @staticmethod
    def _get_correspondence_author_list(article: Article) -> QuerySet:
        """
        Retrieve the list of correspondence authors associated with the given article.

        :param article: The article instance.
        :type article: Article
        :return: Queryset of Account objects representing the correspondence authors.
        :rtype: QuerySet
        :raises: None
        """
        return Account.objects.filter(
            id__in=ArticleAuthorOrder.objects.filter(article=article).values_list("author_id", flat=True)
        )

    def _get_disabled_accounts(self, authors: QuerySet) -> set:
        """
        Identify and return the IDs of disabled accounts based on the given criteria.

        :param authors: A QuerySet of author objects to evaluate
        :type authors: QuerySet
        :return: A set containing the IDs of authors whose accounts are considered disabled
        :rtype: set
        """
        return {
            author.pk
            for author in authors
            if not is_user_eligible_for_correspondence_author(self.instance.journal, author)
        }

    def save(self, commit: bool = True) -> Account:
        """
        Handle only affiliation_country and article.authors.

        The view manages most data due to heavy HTMX usage.
        """
        self.instance.current_step = max(self.instance.current_step, self.step)
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
        fields = [
            "email",
            "first_name",
            "middle_name",
            "last_name",
        ]

    def __init__(self, *args, **kwargs):
        """
        Initialize the form for adding an author to a specific article.

        Binds the form to the Article identified by `article_id` and
        sets required fields for first name, last name, and email.

        :param args: Positional arguments passed to the parent form.
        :param kwargs: Keyword arguments; must include 'article_id'.
        """
        article_id = kwargs.pop("article_id")
        self.is_revision = kwargs.pop("is_revision", False)
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
        model, fk = (
            (RevisionArticleAuthorOrder, {"revision_storage": RevisionStorage.objects.get(article=self.article)})
            if self.is_revision
            else (ArticleAuthorOrder, {"article": self.article})
        )
        model.objects.get_or_create(
            **fk,
            author=instance,
            defaults={"order": self.article.next_author_sort(revision=self.is_revision)},
        )
        return instance


class AddCollaborationForm(forms.ModelForm):
    collaboration_relation = forms.ChoiceField(
        choices=CollaborationRelation.choices,
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
        self.is_revision = kwargs.pop("is_revision", False)
        self.article = Article.objects.get(pk=article_id)
        self.collaboration_relation = kwargs.pop("collaboration_relation", False)
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

        model, fk = (
            (RevisionArticleCollaboration, {"revision_storage": RevisionStorage.objects.get(article=self.article)})
            if self.is_revision
            else (ArticleCollaboration, {"article": self.article})
        )

        model.objects.get_or_create(
            **fk,
            collaboration=instance,
            defaults={
                "relation": self.cleaned_data["collaboration_relation"],
                "order": instance.next_collaboration_sort(article=self.article, revision=self.is_revision),
            },
        )
        return instance


class RevisionStep4Form(SubmissionStep4Form):
    authors_contributions = WjsMiniHTMLFormField(
        label=_("Authors' contribution"),
        height="15rem",
        help_text=_("missing help text"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize a custom form with pre-filled initial data based on revision storage.

        The constructor fetches the associated `RevisionStorage` object for the given `Article` instance
        and initializes specific form fields using data from the `RevisionStorage`. Additionally, it
        filters the queryset for the `correspondence_author` field based on author IDs retrieved
        from the `RevisionArticleAuthorOrder`.

        :param args: Positional arguments passed to the superclass initializer.
        :type args: tuple
        :param kwargs: Keyword arguments passed to the superclass initializer. It must contain the key
            `instance`, which refers to an `Article` instance.
        :type kwargs: dict
        """
        self.revision_storage = RevisionStorage.objects.get(article=kwargs["instance"])
        self.has_author_list_changed = kwargs.pop("has_author_list_changed")
        super().__init__(*args, **kwargs)
        self.fields["authors_contributions"].required = self.has_author_list_changed
        # Using a custom attribute to not trigger bootstrap validation as we use custom logic which checks tinymce
        self.fields["authors_contributions"].widget.attrs["js_required"] = self.has_author_list_changed
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].help_text = _("Required")

    def _get_correspondence_author_list(self, article: Article) -> QuerySet:
        """
        Retrieve the list of correspondence authors associated with the given revision storage.

        :return: Queryset of Account objects representing the correspondence authors.
        :rtype: QuerySet
        :raises: None
        """
        return Account.objects.filter(
            id__in=RevisionArticleAuthorOrder.objects.filter(revision_storage=self.revision_storage).values_list(
                "author_id", flat=True
            )
        )

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

        revision_storage.data["affiliation_country"] = self.cleaned_data.get("country").pk
        revision_storage.data["authors_contributions"] = self.cleaned_data.get("authors_contributions").pk

        author_ids = ArticleAuthorOrder.objects.filter(article=self.instance).values_list("author_id", flat=True)
        revision_storage.data["article_authors"] = list(author_ids)
        revision_storage.save()
        if self.cleaned_data.get("collaboration_relation") == "none":
            RevisionArticleCollaboration.objects.filter(revision_storage=revision_storage).delete()

        return revision_storage.article
