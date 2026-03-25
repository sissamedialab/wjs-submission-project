from core import files as core_files
from core.models import Account, ControlledAffiliation
from django import forms
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from review.models import RevisionRequest
from submission.models import Article, ArticleAuthorOrder, FrozenAuthor

from ..account_validation import (
    ProfileCompletionStatus,
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
    affiliation = forms.ModelChoiceField(queryset=ControlledAffiliation.objects.all())
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
        if "initial" not in kwargs:
            kwargs["initial"] = {}
        kwargs["initial"]["correspondence_author"] = kwargs["instance"].correspondence_author
        if kwargs["initial"]["correspondence_author"]:
            kwargs["initial"]["affiliation"] = kwargs["instance"].correspondence_author.primary_affiliation()
        kwargs["initial"]["collaboration_relation"] = (
            ArticleCollaboration.objects.filter(article=kwargs["instance"]).values_list("relation", flat=True).first()
        ) or CollaborationRelation.NONE
        super().__init__(*args, **kwargs)

        authors_list = self._get_correspondence_author_list(self.instance)
        self.fields["correspondence_author"].queryset = authors_list
        if self.instance.correspondence_author:
            self.fields["affiliation"].queryset = self.instance.correspondence_author.affiliations
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].help_text = _("Required")

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
        return article.author_accounts.all()

    def save(self, commit: bool = True) -> Account:
        """
        Cleanup collaboration_relation on save.

        The view manages most data due to heavy HTMX usage.
        """
        self.instance.current_step = max(self.instance.current_step, self.step)
        instance = super().save()

        instance.submission_data.affiliation = self.cleaned_data.get("affiliation")
        instance.submission_data.save()

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
        self.is_revision = kwargs.pop("is_revision")
        self.article = kwargs.pop("article")
        super().__init__(*args, **kwargs)

        self.fields["first_name"].required = self.instance is None
        self.fields["last_name"].required = self.instance is None
        self.fields["email"].required = self.instance is None
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].help_text = _("Required")

    def save(self, commit: bool = True) -> Account:
        """
        Save the author instance and create an FrozenAuthor entry.

        :param commit: Whether to commit the instance to the database.
        :return: The saved Account instance.
        """
        instance = super().save()
        if self.is_revision:
            model, fk = (
                (RevisionArticleAuthorOrder, {"revision_storage": RevisionStorage.objects.get(article=self.article)})
                if self.is_revision
                else (FrozenAuthor, {"article": self.article})
            )
            model.objects.get_or_create(
                **fk,
                author=instance,
                defaults={"order": self.article.next_author_sort(revision=self.is_revision)},
            )
        else:
            FrozenAuthor.get_or_snapshot_if_email_found(email=instance.email, article=self.article)
        return instance


class AddFrozenAutorObjectForm(forms.Form):
    """
    Associate a frozen author to an article.

    Handle the creation or retrieval of a frozen author object associated with a given
    article and email. This form is intended to manage frozen author objects in the
    context of articles efficiently. It also allows for customization of form initialization
    where revision-specific features might be employed.

    :ivar is_revision: Indicates whether the form instance is being used for a revision
        workflow.
    :type is_revision: bool
    :ivar instance: An object representing details about the author, typically passed
        as an instance to the form.
    :type instance: Any
    :ivar article: An object representing the article associated with the frozen author
        operation.
    :type article: Any
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize an instance of the class and sets up the provided attributes.

        :param args: Positional arguments passed during initialization.
        :param kwargs: Keyword arguments passed during initialization. Expected
            keys include:
            - is_revision (bool): Indicates if the object is a revision.
            - instance: Specifies the instance of the object.
            - article: Specifies the related article.
        """
        self.is_revision = kwargs.pop("is_revision")
        self.instance = kwargs.pop("instance")
        self.article = kwargs.pop("article")
        super().__init__(*args, **kwargs)

    def save(self, commit: bool = True) -> FrozenAuthor:
        """
        Save the current instance and associates it with an author snapshot.

        If an email match is found in the database. If no match is found, a new author
        snapshot is created.

        :param commit: Whether to commit the changes to the database. Defaults to True.
        :type commit: bool
        :return: The author instance that was either fetched or newly created.
        :rtype: FrozenAuthor
        """
        frozen_author, __ = FrozenAuthor.get_or_snapshot_if_email_found(
            email=self.instance.email, article=self.article
        )
        return frozen_author


class AddCollaborationObjectForm(forms.Form):
    """
    Handles the form initialization and saving for adding a collaboration object.

    This class is designed to be used when dealing with collaboration objects,
    allowing instances to be linked to articles or revisions based on the provided
    context. It manages the linkage logic and provides a method to save the
    collaboration to the appropriate model.

    :ivar is_revision: Indicator of whether the collaboration is related to a
        revision. Determines the model and fields to use during saving.
    :type is_revision: bool
    :ivar instance: The collaboration instance to be linked. Represents the main
        collaboration object being processed by the form.
    :type instance: Collaboration
    :ivar article: The article object to which the collaboration is to be linked.
    :type article: Article
    :ivar collaboration_relation: Defines the type of relationship or relation
        between the article and the collaboration instance.
    :type collaboration_relation: str
    :ivar user: The user performing the collaboration operation.
    :type user: User
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize an instance of the class and sets up the provided attributes.

        :param args: Positional arguments to be passed to the superclass initializer.
        :param kwargs: Keyword arguments, including specific ones for initializing the
            instance attributes:

            - is_revision: Indicates whether the entity represents a revision.
            - instance: Represents the instance of the related object.
            - article: Associated article object.
            - collaboration_relation: Denotes the relationship for collaboration.
            - user: User associated with the operation.
        """
        self.is_revision = kwargs.pop("is_revision")
        self.instance = kwargs.pop("instance")
        self.article = kwargs.pop("article")
        self.collaboration_relation = kwargs.pop("collaboration_relation")
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

    def save(self, commit: bool = True) -> RevisionArticleCollaboration | ArticleCollaboration:
        """
        Associate the collaboration instance to the articl.

        It creates or retrieves the appropriate collaboration
        link based on whether the instance is associated with a revision or not. The function
        decides the correct model (either RevisionArticleCollaboration or ArticleCollaboration)
        to use based on the `is_revision` attribute. It then utilizes the foreign key filters
        to retrieve or create a collaboration link and set default attributes where necessary.

        :param commit: Flag indicating whether to persist the save operation immediately
                       after creating or retrieving the collaboration instance.
                       Defaults to `True`.
        :type commit: bool
        :return: The created or retrieved `RevisionArticleCollaboration` or
                 `ArticleCollaboration` instance, based on the `is_revision` attribute.
        :rtype: RevisionArticleCollaboration | ArticleCollaboration
        """
        model, fk_filter = (
            (
                RevisionArticleCollaboration,
                {"revision_storage": RevisionStorage.objects.get(article=self.article)},
            )
            if self.is_revision
            else (ArticleCollaboration, {"article": self.article})
        )
        collaboration_link = model.objects.get_or_create(
            **fk_filter,
            collaboration=self.instance,
            defaults={
                "relation": self.collaboration_relation,
                "order": self.instance.next_collaboration_sort(article=self.article, revision=self.is_revision),
            },
        )
        return collaboration_link  # noqa: RET504


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
        self.is_revision = kwargs.pop("is_revision")
        self.article = kwargs.pop("article")
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
        self.has_author_list_changed = kwargs.pop("has_author_list_changed", False)
        kwargs.setdefault("initial", {})
        kwargs["initial"]["collaboration_relation"] = self.revision_storage.data.get("collaboration_relation")
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

        revision_storage.data["affiliation_pk"] = self.cleaned_data.get("affiliation").pk
        revision_storage.data["authors_contributions"] = self.cleaned_data.get("authors_contributions")

        author_ids = ArticleAuthorOrder.objects.filter(article=self.instance).values_list("author_id", flat=True)
        revision_storage.data["article_authors"] = list(author_ids)
        revision_storage.save()
        if self.cleaned_data.get("collaboration_relation") == "none":
            RevisionArticleCollaboration.objects.filter(revision_storage=revision_storage).delete()

        return revision_storage.article
