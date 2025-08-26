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

    class Meta:
        verbose_name = _("Article submission")
        verbose_name_plural = _("Articles submission")

    def __str__(self):
        return f"ArticleSubmission for {self.article}"
