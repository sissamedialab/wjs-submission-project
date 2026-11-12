from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django import forms
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext_lazy as _
from plugins.wjs_submission.fields import WjsMiniHTMLFormField
from review.logic import render_choices
from submission.models import Article, Field, FieldAnswer
from utils.forms import HTMLDateInput


@dataclass(frozen=True)
class FieldSpec:
    """
    How to build a form field for a Janeway field element kind.

    :param field_class: the form field class to instantiate
    :type field_class: type[django.forms.Field]
    :param widget_class: the widget class, ``None`` to use the default widget of ``field_class``
    :type widget_class: type[django.forms.Widget] | None
    :param widget_attrs: the widget attributes; ``None`` means ``{"div_class": element.width}``
    :type widget_attrs: dict[str, Any] | None
    :param extra_kwargs: callable returning additional form field keyword arguments for an element
    :type extra_kwargs: Callable[[submission.models.Field], dict[str, Any]]
    :param help_text_as_placeholder: render the element help text as the widget placeholder instead of as help text
        (requires ``widget_class``)
    :type help_text_as_placeholder: bool
    """

    field_class: type[forms.Field]
    widget_class: type[forms.Widget] | None = None
    widget_attrs: dict[str, Any] | None = None
    extra_kwargs: Callable[[Field], dict[str, Any]] = field(default=lambda _element: {})
    help_text_as_placeholder: bool = False

    def build(self, element: Field) -> forms.Field:
        """
        Instantiate the form field for ``element``, passing the required flag, help text and widget.

        :param element: the field element to build the form field for
        :type element: submission.models.Field
        :return: the form field
        :rtype: django.forms.Field
        """
        kwargs = {
            "required": element.required,
            "help_text": "" if self.help_text_as_placeholder else element.help_text,
            **self.extra_kwargs(element),
        }
        if self.widget_class:
            attrs = dict(self.widget_attrs) if self.widget_attrs is not None else {"div_class": element.width}
            if self.help_text_as_placeholder:
                attrs["placeholder"] = element.help_text
            kwargs["widget"] = self.widget_class(attrs=attrs)
        return self.field_class(**kwargs)


# Map each Janeway ``submission.models.Field.kind`` to the way its form field is built
FIELD_SPECS: dict[str, FieldSpec] = {
    "text": FieldSpec(forms.CharField, forms.TextInput),
    "textarea": FieldSpec(WjsMiniHTMLFormField),
    "check": FieldSpec(forms.BooleanField, forms.CheckboxInput, widget_attrs={"is_checkbox": True}),
    "date": FieldSpec(forms.CharField, HTMLDateInput),
    "select": FieldSpec(
        forms.ChoiceField,
        forms.Select,
        # The blank choice is first so that nothing is preselected: otherwise the first choice would be silently
        # submitted as the answer, and a required select could never be left unanswered.
        extra_kwargs=lambda element: {"choices": [("", "---------"), *render_choices(element.choices)]},
    ),
    "email": FieldSpec(forms.EmailField, forms.EmailInput),
}


def required_help_text(help_text: str = "") -> SafeString:
    """
    Return the help text of a required field, with only the "Required" keyword in bold.

    The help text is rendered with ``|safe``, so it is kept as is (it may contain markup).
    """
    if help_text:
        return format_html("<strong>{}</strong> - {}", _("Required"), mark_safe(help_text))  # noqa: S308
    return format_html("<strong>{}</strong>", _("Required"))


def map_dynamic_field(element: Field, instance: Article | None) -> forms.Field:
    """
    Build a form field from a submission field element (``submission.models.Field``).

    The form field class, widget and arguments are looked up by element kind in ``FIELD_SPECS``, which covers all
    the Janeway kinds (``text``, ``textarea``, ``check``, ``select``, ``email`` and ``date``). The caller must
    only pass elements of a supported kind: for any other kind ``KeyError`` is raised.
    The field is labelled with the element name and, if the element is required, its help text is
    prefixed with the bold "Required" keyword (see :py:func:`required_help_text`). A required ``textarea`` is also
    flagged with the ``js_required`` widget attribute, because its editor does not render the HTML ``required`` one.
    A ``select`` starts with a blank choice, so that no answer is preselected.

    If ``instance`` is a saved article with an existing :py:class:`submission.models.FieldAnswer` for the element,
    the answer is used as the field's initial value.

    :param element: the field element describing the kind, name, width, help text and required flag
    :type element: submission.models.Field
    :param instance: the article the form is bound to, or ``None`` / an unsaved article
    :type instance: submission.models.Article | None
    :return: the form field
    :rtype: django.forms.Field
    :raises KeyError: if the element kind is not in ``FIELD_SPECS``
    """
    field_obj = FIELD_SPECS[element.kind].build(element)
    field_obj.label = element.name
    if element.required:
        field_obj.help_text = required_help_text(field_obj.help_text)
        if element.kind == "textarea":
            # TinyMCE renders no HTML ``required`` attribute, so flag the field for ``detect_required.js``
            field_obj.widget.attrs["js_required"] = True

    if instance and instance.pk:
        try:
            check_for_answer = FieldAnswer.objects.get(field=element, article=instance)
            field_obj.initial = check_for_answer.answer
        except FieldAnswer.DoesNotExist:
            pass
    return field_obj
