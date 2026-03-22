from django import template
from django.template import Context, Engine, Template
from django.utils.safestring import mark_safe
from journal.models import Issue
from submission.models import Article, KeywordArticle

from ..workflow import Step

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


@register.filter
def step_title(step: Step, article: Article) -> str:
    """
    Retrieve the title for a given step in the context of an article.

    :param step: The step instance for which the title needs to be fetched
    :type step: Step
    :param article: The article instance used to determine the step's title
    :type article: Article
    :return: The title of the step as determined by the article
    :rtype: str
    """
    return step.get_title(article)


@register.simple_tag(takes_context=True)
def render_template_string(context: Context, template_string: str) -> str:
    """
    Render an HTML snippet using the provided template string and context.

    :param context: The context containing variables to be used in the template rendering process
    :type context: Context
    :param template_string: The template string to be rendered into HTML
    :type template_string: str
    :return: The rendered HTML string
    :rtype: str
    :raises TemplateSyntaxError: If the provided template string has invalid syntax
    :raises TemplateDoesNotExist: If the specified template does not exist
    """
    engine = Engine.get_default()
    template = engine.from_string(template_string)
    return template.render(context=context)


@register.filter()
def article_keywords_by_group(article: Article) -> list[KeywordArticle]:
    """
    Return the keywords group of the article.

    Reordering ensure that free keywords are grouped last.

    :param article: The article to get the keywords group for.
    :type article: Article
    :return: Sorted list of keywords by group name, with free keywords grouped last.
    :rtype: list[KeywordArticle]
    """
    return sorted(
        article.keywordarticle_set.all(),
        key=lambda x: (x.keyword.group_id is None, x.keyword.group.name if x.keyword.group_id else ""),
    )
