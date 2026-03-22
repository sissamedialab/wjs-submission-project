import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from submission.models import Article

__all__ = ["create_workflow_handler"]

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Article)
def create_workflow_handler(sender, instance, created, **kwargs):
    """Create :py:class:`ArticleSubmission` when an article is created."""
    from .models import ArticleSubmission  # noqa: PLC0415

    __, created_recreated = ArticleSubmission.objects.get_or_create(article=instance)
    # ArticleSubmission should be created only after the article has been created
    # but some user-reported errors points to some possible error here, logging the not-expected cases for
    # investigation
    if not created and created_recreated:
        logger.debug("Article submission created after step one - this is not expected")
