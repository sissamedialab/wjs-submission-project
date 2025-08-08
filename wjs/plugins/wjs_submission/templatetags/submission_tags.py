from django import template
from django.template import Context, Template
from django.utils.safestring import mark_safe
from journal.models import Issue

register = template.Library()


# FIXME: this code was copied as is from WJS
@register.filter
def display_title(issue: Issue | None, use_short=False) -> str:
    """Return a translatable display_title for issues."""
    if not issue:
        return ""
    if issue.issue_type.code == "collection":
        volume, issue_number, year, issue_title, *__ = issue.issue_title_parts()
        if use_short and issue.short_name:
            title = issue.short_name
        elif issue.short_name:
            title = f"{issue_title} ({issue.short_name})"
        else:
            title = issue_title
        template = Template(
            " &bull; ".join((volume, issue_number, year, title)),  # noqa FLY002
        )
        return mark_safe(template.render(Context()))  # noqa S308
    return mark_safe(issue.update_display_title(save=False))  # noqa S308
