"""
Django management command to reset dangling FieldAnswer objects for JCOM/JCOMAL articles.

This command scans articles from JCOM and JCOMAL journals to identify and handle
FieldAnswer objects with null Field foreign keys (dangling answers). These occur when
checklist items are removed or renamed. The command either:
- Deletes FieldAnswer objects with value "on" (linked to removed fields)
- Reassigns other FieldAnswer objects to the new AI-related field

Usage:
    python manage.py reset_field_answers
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import QuerySet
from journal.models import Journal
from plugins.wjs_submission import settings
from submission.models import Article, Field, FieldAnswer


class Command(BaseCommand):
    """
    Scan articles for specific journals and cleanup dangling FieldAnswer.

    Identify dangling FieldAnswer objects, and ensures that they are either reset to the correct field or deleted
    if not applicable. Its purpose is to maintain data integrity in FieldAnswer associations.

    :ivar help: Description of the command's functionality displayed in the help text.
    :type help: str
    """

    help = "Reset dangling FieldAnswer objects for JCOM/JCOMAL articles by deleting or reassigning them"

    @staticmethod
    def _select_articles(journal: Journal) -> QuerySet[Article]:
        """
        Filter articles based on the specified journal code and checks if there are no linked field answers.

        :param journal: Code of the journal to filter articles for. Must be a string.
        :return: QuerySet containing the filtered articles meeting the specified criteria.
        :rtype: QuerySet
        """
        return Article.objects.filter(journal__code=journal, fieldanswer__field__isnull=True)

    @staticmethod
    def _reset_field_answer(article: Article) -> None:
        """
        Reset field answers related to the given article by changing the associated field to a new AI-related field.

        Remove other answers if their linked field is not set, if use of ai field has already been set, the old value
        is dropped.

        :param article: The Article instance whose field answers need to be reset.
        :type article: Article
        :return: None
        """
        new_ai_field = Field.objects.filter(journal=article.journal, name=settings.USE_OF_AI_FIELD_LABEL).first()
        if not new_ai_field:
            raise CommandError(
                f"Field '{settings.USE_OF_AI_FIELD_LABEL}' not found for journal {article.journal.code}"
            )
        existing_ai_answer = FieldAnswer.objects.filter(field=new_ai_field, article=article).exists()
        for answer in article.fieldanswer_set.filter(field__isnull=True):
            # Fields with "on" value have been dropped from submission and we can safely delete them
            # If the new AI field has already been populated (during the revision) we can safely delete the old value
            if answer.answer == "on" or existing_ai_answer:
                answer.delete()
            # If the new AI field has not been populated the old value is copied to the new field
            else:
                answer.field = new_ai_field
                answer.save()

    def handle(self, *args, **options):
        """
        Scan articles for JCOM / JCOMAL and reset any dangling FieldAnswer object.

        Two checklist items have been removed, one has been renamed: in any case the FieldAnswer object have the
        Field foreign key set to null.

        FieldAnswer linked to removed fields can be deleted, the renamed one must be linked to the new Field.
        """
        journals = ["JCOM", "JCOMAL"]
        for journal in journals:
            articles = self._select_articles(journal)
            for article in articles:
                self._reset_field_answer(article)
