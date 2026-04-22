from core.models import Account, Country
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from submission.models import Article, ArticleAuthorOrder, ArticleFunding

from .settings import ARXIV_BASE_DOI
from .signals import *  # noqa


class ArticleSubmission(models.Model):
    class CasDeclaration(models.TextChoices):
        NO = "no", _("My article has no associated code or the code will not be deposited")
        ESM = "esm", _("My article has code included as electronic supplementary material")
        URL = "url", _("My article has associated code in a repository")

        @classmethod
        def as_dict(cls) -> dict[str, str]:
            """
            Convert the choices attribute to a dictionary representation.

            :return: A dictionary mapping the keys and values of choices
            :rtype: dict[str, str]
            """
            return dict(cls.choices)

    class DasDeclaration(models.TextChoices):
        NO = "no", _("My article has no associated data or the data will not be deposited")
        ESM = "esm", _("My article has data included as electronic supplementary material")
        URL = "url", _("My article has associated data in a repository")

        @classmethod
        def as_dict(cls) -> dict[str, str]:
            """
            Convert the choices attribute to a dictionary representation.

            :return: A dictionary mapping the keys and values of choices
            :rtype: dict[str, str]
            """
            return dict(cls.choices)

    class ManuscriptSourceFormat(models.TextChoices):
        AUTO = "auto", _("Auto")
        LATEX = "latex", _("Tex / LaTeX")
        DOC = "doc", _("Documents (odt/docx/rtf)")

        def as_dict(self) -> dict[str, str]:
            """
            Convert the choices attribute to a dictionary representation.

            :return: A dictionary mapping the keys and values of choices
            :rtype: dict[str, str]
            """
            return dict(self.choices)

    class TexEngine(models.TextChoices):
        TEX = "tex", _("Tex")
        LATEX = "latex", _("LaTex")
        PDFLATEX = "pdflatex", _("PdflLaTex")
        XELATEX = "xelatex", _("XeLaTex")

        def as_dict(self) -> dict[str, str]:
            """
            Convert the choices attribute to a dictionary representation.

            :return: A dictionary mapping the keys and values of choices
            :rtype: dict[str, str]
            """
            return dict(self.choices)

    article = models.OneToOneField(
        Article,
        verbose_name=_("Article"),
        on_delete=models.CASCADE,
        related_name="submission_data",
    )
    arxiv_category = models.CharField(max_length=30, verbose_name=_("Arxiv category"), default="", blank=True)

    cover_letter_file = models.ForeignKey(
        "core.File",
        null=True,
        blank=True,
        related_name="cover_letter_file",
        on_delete=models.SET_NULL,
    )
    cas = models.CharField(
        max_length=255,
        verbose_name=_("CAS declaration"),
        choices=CasDeclaration.choices,
        default="",
    )
    cas_url = models.URLField(verbose_name=_("CAS URL"), default="")
    das = models.CharField(
        max_length=255,
        verbose_name=_("DAS declaration"),
        choices=DasDeclaration.choices,
        default="",
    )
    das_url = models.URLField(verbose_name=_("DAS URL"), default="")
    access_mode = models.ForeignKey("AccessMode", on_delete=models.SET_NULL, null=True, blank=True)
    special_request = models.TextField(verbose_name=_("Special request"), blank=True, default="")
    use_of_ai_flag = models.BooleanField(verbose_name=_("Use of AI"), default=False)

    cover_letter_file_allowed_extension = [".pdf", ".docx", ".doc", ".odt", ".rtf"]

    affiliation_country = models.ForeignKey(
        Country,
        null=True,
        blank=True,
        verbose_name=_("Affiliation country"),
        on_delete=models.SET_NULL,
    )

    feedback_uuid = models.UUIDField(
        verbose_name=_("Feedback UUID"),
        blank=True,
        null=True,
        help_text=_("Unique identifier for websocket feedback channel"),
    )

    class Meta:
        verbose_name = _("Article submission")
        verbose_name_plural = _("Articles submission")

    def __str__(self):
        return f"ArticleSubmission for {self.article}"

    def save(
        self,
        *,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None,
    ):
        """
        Save the current instance to the database, applying specific access mode rules if applicable.

        :param force_insert: Force an SQL INSERT operation, even if the object has a primary key
        :type force_insert: bool
        :param force_update: Force an SQL UPDATE operation, even if the object is new
        :type force_update: bool
        :param using: The database alias to use for the save operation
        :type using: str or None
        :param update_fields: Specify names of fields to update if performing an update operation
        :type update_fields: list[str] or None
        """
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)
        if self.access_mode:
            try:
                journal_access_mode_parameters = AccessModeJournal.objects.filter(
                    access_mode=self.access_mode, journal=self.article.journal
                )
                if journal_access_mode_parameters.exists():
                    self.article.licence = journal_access_mode_parameters.first().licence
                    self.article.rigths = journal_access_mode_parameters.first().copyright
            except AccessModeJournal.DoesNotExist:
                # ignoring configuration error to avoid breaking submission process
                pass

    def get_arxiv_id(self) -> str:
        """
        Retrieve the arXiv identifier for the associated article.

        :raises AttributeError: If the `article` object does not have the `get_identifier` method.
        :raises ValueError: If the `article.get_identifier('arxiv')` call returns an invalid result.

        :return: The arXiv identifier for the article.
        :rtype: str
        """
        return self.article.get_identifier("arxiv")

    def get_arxiv_doi(self) -> str:
        """
        Retrieve the DOI URL for the arXiv paper.

        The method constructs the DOI URL using the format specified by arXiv and the
        arXiv ID returned by the `get_arxiv_id` method.

        :return: The DOI URL as a string.
        :rtype: str
        :raises: AttributeError if `get_arxiv_id` is not callable or does not return a valid value.
        """
        versionless_arxiv_id = self.get_arxiv_id().partition("v")[0]
        return f"{ARXIV_BASE_DOI}/arXiv.{versionless_arxiv_id}"


class CollaborationRelation(models.TextChoices):
    BY = "by", _("by a collaboration")
    ON_BEHALF_OF = "on_behalf_of", _("on behalf of a collaboration")
    NONE = "none", _("No collaboration involved")


class Collaboration(models.Model):
    name = models.CharField(max_length=255)
    institutional_email = models.EmailField(blank=True, help_text=_("If available"))
    logo = models.ForeignKey(
        "core.File",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text=_("Logo representing this collaboration"),
    )
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    public_listing = models.BooleanField(
        default=False,
        verbose_name=_("Approved for public listing"),
        help_text=_("If set, this collaboration is visible in the selection list"),
    )
    creator = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_collaborations",
        help_text=_("The account that created this collaboration"),
    )
    linked_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_collaborations",
        help_text=_("The account automatically added to the authors list when a collaboration is added"),
    )

    class Meta:
        verbose_name = _("Collaboration")
        verbose_name_plural = _("Collaborations")
        ordering = ("name",)

    def __str__(self):
        return self.name

    @staticmethod
    def next_collaboration_sort(article: Article, revision: bool = False) -> int:
        """
        Use to get the correct value for the order field when a new collaboration is created.

        Similar to Janeway's "next_author_sort()".
        """
        model = RevisionArticleCollaboration if revision else ArticleCollaboration
        filters = (
            {"revision_storage": RevisionStorage.objects.get(article=article)} if revision else {"article": article}
        )
        current_orders = model.objects.filter(**filters).values_list("order", flat=True)
        return (max(current_orders) + 1) if current_orders else 0


class ArticleCollaboration(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="collaborations")
    collaboration = models.ForeignKey(Collaboration, on_delete=models.CASCADE, related_name="articles")
    relation = models.CharField(
        max_length=32,
        choices=CollaborationRelation.choices,
        default="by",
        help_text=_("Indicates whether the article was written by or on behalf of the collaboration"),
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text=_("Order of this collaboration in the author/collaboration list"),
    )

    class Meta:
        ordering = ("order",)
        unique_together = ("article", "collaboration")

    def __str__(self):
        # relation code must-be "unslugified" to be displayed in the UI, the display label is meant for form options
        return f"{self.relation.replace('_', ' ')} {self.collaboration}"


class AccessMode(models.Model):
    name = models.CharField(_("Name"), max_length=255)
    code = models.SlugField(_("Code"), max_length=255)
    user_selectable = models.BooleanField(_("User selectable"), default=True)

    class Meta:
        verbose_name = _("Access mode")
        verbose_name_plural = _("Access modes")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Populate code field if empty.
        """
        if not self.code:
            self.code = slugify(self.name)
        return super().save(*args, **kwargs)


class AccessModeJournal(models.Model):
    access_mode = models.ForeignKey(AccessMode, on_delete=models.CASCADE, related_name="parameters")
    journal = models.ForeignKey(
        "journal.Journal",
        on_delete=models.CASCADE,
        related_name="access_mode_parameters",
    )
    licence = models.ForeignKey(
        "submission.Licence",
        on_delete=models.CASCADE,
        related_name="access_mode_parameters",
    )
    copyright = models.CharField(_("Copyright declaration"), max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("Journal / Access mode connection")
        verbose_name_plural = _("Journal / Access mode connections")

    def __str__(self):
        return f"{self.access_mode} / {self.journal}"


class RevisionStorage(models.Model):
    """
    Temporary storage of draft-revision data.

    The revision process can be longish, and we don't want to store half-backed data in their final destination.
    This (short-lived) records will keep the data while the author completes all the steps of the revision submission.
    """

    class RevisionFlowType(models.TextChoices):
        CONFIRM = "confirm", _("Confirmation of previous version")
        METADATA = "metadata", _("Metadata change")
        FULL = "full", _("Revision submission")

    article = models.OneToOneField(
        Article,
        on_delete=models.CASCADE,
    )
    data = models.JSONField(
        verbose_name=_("Draft data"),
        default=dict,
        blank=True,
    )
    revision_flow_type = models.CharField(_("Revision flow type"), max_length=10, choices=RevisionFlowType.choices)
    revision_step = models.PositiveSmallIntegerField(_("Current revision step"), default=0)

    class Meta:
        verbose_name = _("Draft article")
        verbose_name_plural = _("Draft articles")

    def __str__(self):
        return f"Revision storage for {self.article.journal.code}_{self.article.id}"


class RevisionArticleAuthorOrder(models.Model):
    revision_storage = models.ForeignKey(
        RevisionStorage,
        on_delete=models.CASCADE,
    )
    author = models.ForeignKey(
        "core.Account",
        on_delete=models.CASCADE,
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order",)

    def __str__(self):
        return f"{self.revision_storage.article} {self.author}"


class RevisionArticleCollaboration(models.Model):
    revision_storage = models.ForeignKey(RevisionStorage, on_delete=models.CASCADE, related_name="collaborations")
    collaboration = models.ForeignKey(Collaboration, on_delete=models.CASCADE, related_name="revision_storages")
    relation = models.CharField(
        max_length=32,
        choices=CollaborationRelation.choices,
        default="by",
        help_text=_("Indicates whether the article was written by or on behalf of the collaboration"),
    )
    order = models.PositiveIntegerField(
        default=0, help_text=_("Order of this collaboration in the author/collaboration list")
    )

    class Meta:
        ordering = ("order",)
        unique_together = ("revision_storage", "collaboration")

    def __str__(self):
        return f"{self.relation} {self.collaboration}"


def next_author_sort(self, revision: bool = False, *args, **kwargs) -> int:
    model = RevisionArticleAuthorOrder if revision else ArticleAuthorOrder
    filters = {"revision_storage": RevisionStorage.objects.get(article=self)} if revision else {"article": self}
    current_orders = model.objects.filter(**filters).values_list("order", flat=True)
    return (max(current_orders) + 1) if current_orders else 0


Article.next_author_sort = next_author_sort


class SubmissionArticleFunding(ArticleFunding):
    country = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.name


class RevisionSubmissionArticleFunding(models.Model):
    revision_storage = models.ForeignKey(RevisionStorage, on_delete=models.CASCADE, related_name="funding")
    name = models.CharField(
        max_length=500,
        blank=False,
        null=False,
        help_text="Funder name",
    )
    fundref_id = models.CharField(  # noqa: DJ001
        max_length=500,
        blank=True,
        default="",
        null=True,
        help_text="Funder DOI (optional). Enter as a full Uniform "
        "Resource Identifier (URI), such as "
        "https://dx.doi.org/10.13039/501100021082",
    )
    funding_id = models.CharField(  # noqa: DJ001
        max_length=500,
        blank=True,
        default="",
        null=True,
        help_text="The grant ID (optional). Enter the ID by itself",
    )
    funding_statement = models.TextField(  # noqa: DJ001
        blank=True,
        help_text=_("Additional information regarding this funding entry"),
        null=True,
    )
    country = models.CharField(max_length=128, blank=True, null=True)  # noqa: DJ001

    def __str__(self):
        return self.name

    @property
    def article(self) -> Article:
        """
        Get the article associated with the current revision.

        :return: The article object associated with the current revision.
        :rtype: Article
        """
        return self.revision_storage.article


class WhitelistedCorrespondenceAuthors(models.Model):
    """
    Represents a whitelisted correspondence author.

    This model is used to store information about authors who are allowed
    to be set as corresponding author bypassing validation logic in
    :py:func:`wjs.plugins.wjs_submission.account_validation.wjs.plugins.wjs_submission.account_validation.is_user_eligible_for_correspondence_author

    :ivar user: The account associated with the whitelisted author.
    :type user: Account
    :ivar journal: The journal to whitelist author on.
    :type journal: Journal
    :ivar validity_start_date: The optional start date indicating the validity period of
        the author's whitelist status.
    :type validity_start_date: datetime.date or None
    :ivar validity_stop_date: The optional end date indicating the validity period of
        the author's whitelist status.
    :type validity_stop_date: datetime.date or None
    """

    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    journal = models.ForeignKey("journal.Journal", on_delete=models.CASCADE)
    validity_start_date = models.DateField(null=True, blank=True)
    validity_stop_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = _("Whitelisted correspondence author")
        verbose_name_plural = _("Whitelisted correspondence authors")

    def __str__(self):
        return f"{self.user.email} ({self.validity_start_date or ''} - {self.validity_stop_date or ''})"
