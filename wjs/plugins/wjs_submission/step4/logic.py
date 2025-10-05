from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


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
    article: object

    def delete(self, item, item_obj):
        """
        Delete the entity instance.

        Applies additional rules when deleting authors:
        the owner and correspondence author cannot be deleted.
        """
        if self.item_field == "author":
            if item_obj == self.article.owner:
                msg = _("Can't delete owner %s") % self.item_field
                raise ValidationError(msg)
            if item_obj == self.article.correspondence_author:
                raise ValidationError(_("Can't delete correspondence author"))
        item.delete()

    def move_up(self, item):
        """
        Move the entity one position up.

        Swaps order with the closest preceding entity.
        """
        swap_with = (
            self.model.objects.filter(
                article=self.article,
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
                article=self.article,
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
        item_order = getattr(item, self.order_field)
        swap_order = getattr(swap_with, self.order_field)
        setattr(item, self.order_field, swap_order)
        setattr(swap_with, self.order_field, item_order)
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
            msg = _("Unsupported action: %s") % self.action
            raise ValidationError(msg)
