"""
Django management command to enable hierarchical keywords for the configured journals.

Usage:
    python manage.py enable_hierarchical_keywords
"""

from django.core.management.base import BaseCommand
from submission.models import SubmissionConfiguration

from ... import settings as submission_settings


class Command(BaseCommand):
    help = "Enable hierarchical keywords for the journals listed in HIERARCHICAL_KEYWORDS_JOURNALS"

    def handle(self, *args, **options):
        """
        Set hierarchical_keywords to True for the configured journals.

        :param args: Positional arguments (not used).
        :param options: Command-line options (not used).
        :return: None
        """
        journal_codes = submission_settings.HIERARCHICAL_KEYWORDS_JOURNALS
        updated = SubmissionConfiguration.objects.filter(
            journal__code__in=journal_codes,
        ).update(hierarchical_keywords=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"Hierarchical keywords enabled for {updated} of {len(journal_codes)} "
                f"configured journals ({', '.join(journal_codes)}).",
            ),
        )
        if updated < len(journal_codes):
            self.stdout.write(
                self.style.WARNING("Some configured journals do not exist in this database (skipped)."),
            )
