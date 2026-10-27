from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext_lazy as _


def required_help_text(help_text: str = "") -> SafeString:
    """
    Return the help text of a required field, with only the "Required" keyword in bold.

    The help text is rendered with ``|safe``, so it is kept as is (it may contain markup).
    """
    if help_text:
        return format_html("<strong>{}</strong> - {}", _("Required"), mark_safe(help_text))  # noqa: S308
    return format_html("<strong>{}</strong>", _("Required"))
