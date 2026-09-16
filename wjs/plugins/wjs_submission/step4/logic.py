from dataclasses import dataclass

from core.models import Account, ControlledAffiliation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from submission.models import Article, FrozenAuthor

from ..models import RevisionArticleAuthorOrder, RevisionStorage
from ..workflow import is_revision


@dataclass
class TableMoveDeleteHandler:
    """
    Handler for table item manipulation.

    Supports delete, move up, and move down in ordered
    article-related models such as authors or collaborations.

    Attributes:
        model: Django model class to operate on.
        entity_id: Primary key of the target entity.
        item_field: Attribute name on the model that points to the related object
            (e.g., "author", "collaboration").
        order_field: Attribute name used to define ordering within the table.
        action: Action to perform ("delete", "move_up", "move_down").
        article: The article instance associated with the entity.

    """

    model: type
    entity_id: int
    item_field: str
    order_field: str
    action: str
    parent_obj: object
    parent_field: str = "article"

    def delete(self, item, item_obj):
        """
        Delete the entity instance.

        Applies additional rules when deleting authors:
        the owner and correspondence author cannot be deleted.
        """
        if self.item_field == "author":
            if item_obj.pk == getattr(self.parent_obj, "owner", None):
                raise ValidationError(_("Can't delete owner %s") % self.item_field)
            if item_obj.pk == getattr(self.parent_obj, "correspondence_author", None):
                raise ValidationError(_("Can't delete correspondence author"))
        item.delete()

    def move_up(self, item):
        """
        Move the entity one position up.

        Swaps order with the closest preceding entity.
        """
        swap_with = (
            self.model.objects.filter(
                **{self.parent_field: self.parent_obj},
                **{f"{self.order_field}__lt": getattr(item, self.order_field)},
            )
            .order_by(f"-{self.order_field}")
            .first()
        )
        self._swap(item, swap_with)

    def move_down(self, item):
        """
        Move the entity one position down.

        Swaps order with the closest succeeding entity if available.
        """
        swap_with = (
            self.model.objects.filter(
                **{self.parent_field: self.parent_obj},
                **{f"{self.order_field}__gt": getattr(item, self.order_field)},
            )
            .order_by(self.order_field)
            .first()
        )
        self._swap(item, swap_with)

    def _swap(self, item, swap_with):
        """
        Swap the order value with another entity.

        Only performs the swap if a candidate exists.
        """
        if not swap_with:
            return
        o1, o2 = getattr(item, self.order_field), getattr(swap_with, self.order_field)
        setattr(item, self.order_field, o2)
        setattr(swap_with, self.order_field, o1)
        item.save()
        swap_with.save()

    def run(self):
        """
        Execute the configured action.

        Supported actions are "delete", "move_up", and "move_down".
        """
        item = self.model.objects.get(pk=self.entity_id)
        item_obj = getattr(item, self.item_field)

        if self.action == "delete":
            self.delete(item, item_obj)
        elif self.action == "move_up":
            self.move_up(item)
        elif self.action == "move_down":
            self.move_down(item)
        else:
            raise ValidationError(_("Unsupported action: %s") % self.action)


def has_author_list_changed(article):
    """
    Determine if the list of authors associated with an article has changed.

    This function compares the authors associated with the current version
    of an article against the authors stored in its revision history. If the
    two sets of authors differ, it indicates that the author list has changed.

    :param article: The article instance whose author list is being checked.
    :type article: Article
    :return: A boolean indicating whether the list of authors has changed.
    :rtype: bool
    """
    try:
        revision_storage = article.revisionstorage
        revision_authors = set(
            RevisionArticleAuthorOrder.objects.filter(revision_storage=revision_storage).values_list(
                "author_id", flat=True
            )
        )
    except RevisionStorage.DoesNotExist:
        revision_authors = set()

    current_authors = set(FrozenAuthor.objects.filter(article=article).values_list("author_id", flat=True))

    return revision_authors != current_authors


@dataclass
class SaveCorrespondenceAuthor:
    """
    Set the correspondence author of an article, keeping the stored affiliation consistent with it.

    The stored affiliation is one of the correspondence author affiliations, so when the author changes
    the affiliation is reset to the primary affiliation of the new one: the previous value belongs to
    somebody else and is not selectable any more.

    During a revision both values are stored in the revision storage, because the article and its
    submission data are left untouched until the revision is submitted.

    Attributes:
        article: The article whose correspondence author is being set.
        author: The account to set as correspondence author.

    """

    article: Article
    author: Account

    def _get_revision_storage(self) -> RevisionStorage | None:
        """Return the locked storage of the revision in progress, if the article is being revised."""
        if not is_revision(self.article):
            return None
        return RevisionStorage.objects.select_for_update().get(article=self.article)

    def _has_author_changed(self, revision_storage: RevisionStorage | None) -> bool:
        """Tell if the given author is not the one currently set."""
        if revision_storage:
            return str(revision_storage.data.get("correspondence_author")) != str(self.author.pk)
        return self.article.correspondence_author_id != self.author.pk

    def _save_revision(self, revision_storage: RevisionStorage, affiliation: ControlledAffiliation | None):
        """Store author and affiliation in the revision storage."""
        revision_storage.data["correspondence_author"] = self.author.pk
        revision_storage.data["affiliation_pk"] = affiliation.pk if affiliation else None
        revision_storage.save()

    def _save_article(self, affiliation: ControlledAffiliation | None):
        """Store the author on the article and the affiliation in its submission data."""
        self.article.correspondence_author = self.author
        self.article.save()
        self.article.submission_data.affiliation = affiliation
        self.article.submission_data.save()

    def run(self):
        """Set the correspondence author, resetting the affiliation when the author changes."""
        with transaction.atomic():
            revision_storage = self._get_revision_storage()
            if not self._has_author_changed(revision_storage):
                return None
            affiliation = self.author.primary_affiliation()
            if revision_storage:
                self._save_revision(revision_storage, affiliation)
            else:
                self._save_article(affiliation)
            return revision_storage
