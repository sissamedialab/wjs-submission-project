from django.db.models.signals import post_save
from django.dispatch import receiver
from submission.models import Article

__all__ = ["create_workflow_handler"]


@receiver(post_save, sender=Article)
def create_workflow_handler(sender, instance, created, **kwargs):
    """Create :py:class:`ArticleSubmission` when an article is created."""
    from .models import ArticleSubmission  # noqa: PLC0415

    if not created:
        return
    ArticleSubmission.objects.create(article=instance)
