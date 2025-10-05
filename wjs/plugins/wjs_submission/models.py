from core.models import Account, Country
from django.db import models
from django.utils.translation import gettext_lazy as _
from submission.models import Article

from .signals import *  # noqa: F403


class ArticleSubmission(models.Model):
    article = models.OneToOneField(
        Article,
        verbose_name=_("Article"),
        on_delete=models.CASCADE,
        related_name="submission_data",
    )
    arxiv_category = models.CharField(max_length=30, verbose_name=_("Arxiv category"), default="", blank=True)

    cover_letter_file = models.ForeignKey(
        "core.File", null=True, blank=True, related_name="cover_letter_file", on_delete=models.SET_NULL
    )
    cover_letter_file_allowed_extension = [".pdf", ".docx", ".doc", ".odt", ".rtf"]

    affiliation_country = models.ForeignKey(
        Country,
        null=True,
        blank=True,
        verbose_name=_("Affiliation country"),
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = _("Article submission")
        verbose_name_plural = _("Articles submission")

    def __str__(self):
        return f"ArticleSubmission for {self.article}"


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
    def next_collaboration_sort(article: Article) -> int:
        """
        Use to get the correct value for the order field when a new collaboration is created.

        Similar to Janeway's "next_author_sort()".
        """
        current_orders = ArticleCollaboration.objects.filter(article=article).values_list("order", flat=True)
        if not current_orders:
            return 0
        return max(current_orders) + 1


class ArticleCollaboration(models.Model):
    class Relations(models.TextChoices):
        BY = "by", _("by a collaboration")
        ON_BEHALF_OF = "on_behalf_of", _("on behalf of a collaboration")
        NONE = "none", _("No collaboration involved")

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="collaborations")
    collaboration = models.ForeignKey(Collaboration, on_delete=models.CASCADE, related_name="articles")
    relation = models.CharField(
        max_length=32,
        choices=Relations.choices,
        default="by",
        help_text=_("Indicates whether the article was written by or on behalf of the collaboration"),
    )
    order = models.PositiveIntegerField(
        default=0, help_text=_("Order of this collaboration in the author/collaboration list")
    )

    class Meta:
        ordering = ("order",)
        unique_together = ("article", "collaboration")

    def __str__(self):
        return f"{self.relation} {self.collaboration}"
