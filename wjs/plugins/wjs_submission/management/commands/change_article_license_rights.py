"""
Django management command to fix license, rights for JCOM/JCOMAL articles.

Usage:
    python manage.py change_article_license_rights
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from submission.models import STAGE_PUBLISHED, Article, Licence


class Command(BaseCommand):
    """
    Django management command to fix license, rights for JCOM/JCOMAL articles.
    """

    help = "Django management command to fix license, rights for JCOM/JCOMAL articles."

    def handle(self, *args, **options):  # noqa: PLR6301
        """
        Fix license, rights for JCOM/JCOMAL articles.
        """
        for journal_code in ["JCOM", "JCOMAL"]:
            articles = Article.objects.filter(stage=STAGE_PUBLISHED, journal__code=journal_code)
            old_license = Licence.objects.get(journal__code=journal_code, short_name="CC BY 4.0")
            new_license = Licence.objects.get(journal__code=journal_code, short_name="CC BY-NC-ND 4.0")
            for article in articles:
                if not article.license and article.date_published:
                    if article.date_published < datetime(2026, 1, 1, tzinfo=timezone.get_current_timezone()):
                        article.license = new_license
                    else:
                        article.license = old_license

                if not article.rights:
                    article.rights = "<p>© Authors</p>"

                article.save()
