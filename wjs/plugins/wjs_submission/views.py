import logging

from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q, QuerySet
from django.http import HttpResponseBase, JsonResponse
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import RedirectView, TemplateView
from submission.models import Article, Keyword
from submission.views import KeywordAutocomplete
from utils.setting_handler import get_setting

from .arxiv import (
    ArticleAlreadySubmittedError,
    ArXivIDContinueSubmissionError,
    ArXivIDNotFoundError,
    ArXivQueryError,
    ArXivToWjsArticle,
)
from .mixins import AuthorFilteringView, HtmxMixin
from .workflow import STEPS

logger = logging.getLogger(__name__)

# Errors caused by the author's input (not by WJS or arXiv): logged without traceback
ARXIV_USER_ERRORS = (ArXivIDNotFoundError, ArXivIDContinueSubmissionError, ArticleAlreadySubmittedError)
# Errors whose message is meant for the author: any other error is reported with a generic message, to avoid exposing
# internal details (its details are logged).
# NB: ArXivQueryError covers all its subclasses (ArXivIDNotFoundError, ArXivConnectionError, ...);
# ArticleAlreadySubmittedError is listed explicitly because it is a ValidationError, not an ArXivQueryError.
ARXIV_USER_FACING_ERRORS = (ArXivQueryError, ArticleAlreadySubmittedError)


class Manager(UserPassesTestMixin, TemplateView):
    """Plugin manager page. Just an index."""

    template_name = "wjs_submission/index.html"

    def test_func(self):
        """Verify that only staff can access."""
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)


class RedirectToComplete(AuthorFilteringView, RedirectView):
    """Redirect to the article submission complete page."""

    model = Article
    pk_url_kwarg = "article_id"

    def get_queryset(self) -> QuerySet:
        """
        Filter the base queryset to include only articles for which the current user is owner or correspondence author.

        :return: Queryset of articles.
        :rtype: QuerySet[Article]
        """
        return (
            self.model.objects.filter(
                Q(owner=self.request.user) | Q(correspondence_author=self.request.user) | Q(authors=self.request.user)
            )
            .filter(journal=self.request.journal)
            .distinct()
        )

    def get_object(self, queryset=None) -> Article:
        """Get current article from URL parameter."""
        return self.get_queryset().get(pk=self.kwargs["article_id"])

    def get(self, request, *args, **kwargs) -> HttpResponseBase:
        """Handle get request to redirect or send to error page if article is not accessible."""
        try:
            self.object = self.get_object()
            return super().get(request, *args, **kwargs)
        except Article.DoesNotExist:
            return self.handle_no_permission()

    def get_redirect_url(self, *args, **kwargs) -> str:
        """
        Calculate the redirect URL for the given article.
        """
        return reverse(
            "wjs_article_details_from_id",
            kwargs={"article_id": self.object.id},
        )


class ClosedSubmissionsView(AuthorFilteringView, TemplateView):
    """Redirect to the article submission complete page."""

    template_name = "wjs_submission/closed.html"


class SubmissionLastStepRedirectView(AuthorFilteringView, RedirectView):
    def get_redirect_url(self, *args, **kwargs):  # noqa: PLR6301
        """
        Redirect to first incomplete step of the article.

        :return: Next step URL.
        """
        article = Article.objects.get(pk=kwargs["article_id"])
        step = STEPS.get(article.current_step, STEPS[1])

        return step.get_incomplete_step_url(article)


class ArxivMicroservice(HtmxMixin, AuthorFilteringView, View):
    def post(self, request, *args, **kwargs):
        """
        Handle POST requests to validate an arXiv ID and convert the article into a system-specific format.

        :param request: The HTTP request object for the POST operation
                        containing necessary data.
        :param args: Additional positional arguments passed to the function.
        :param kwargs: Additional keyword arguments passed to the function.
        :return: JsonResponse indicating the success or failure of the operation.
        """
        arxiv_id = request.POST.get("arxiv_id", "").strip()
        arxiv_article_id = request.POST.get("arxiv_article_id", 0) or 0
        service = ArXivToWjsArticle(arxiv_id=arxiv_id, arxiv_article_id=arxiv_article_id, request=self.request)
        try:
            article = service.run()
            return JsonResponse(
                {
                    "article_id": article.pk,
                    "status": "success",
                    "message": f'Validated for "{article.title}"',
                }
            )
        except Exception as e:  # noqa: BLE001
            self._log_error(e, arxiv_id, arxiv_article_id)
            if isinstance(e, ARXIV_USER_FACING_ERRORS):
                error_msg = str(e)
            else:
                error_msg = self._get_unexpected_error_message(e)
            # horrible trick to ensure arXiv string is correctly read by the screen reader
            replacements = {
                "arxiv.org": (
                    '<span class="visually-hidden">archive.org</span><span aria-hidden="true">arxiv.org</span>'
                ),
                "arXiv": '<span class="visually-hidden">archive</span><span aria-hidden="true">arXiv</span>',
                "arXiv ID": '<span class="visually-hidden">archive ID</span><span aria-hidden="true">arXiv ID</span>',
            }
            for key, value in replacements.items():
                error_msg = error_msg.replace(key, value)
            error_msg = mark_safe(error_msg)  # noqa: S308
            return JsonResponse({"status": "error", "message": f"Error: {error_msg}"}, status=500)

    def _get_unexpected_error_message(self, error: Exception) -> str:
        """
        Return a generic message for errors whose message is not meant for the author.

        The error details are appended only in DEBUG mode (escaped, since the message is rendered as HTML).
        """
        support_email = get_setting("general", "support_email", self.request.journal).processed_value
        msg = (
            "An unexpected error occurred while importing the preprint from arXiv. Please try again later or contact "
            f"{escape(support_email)} for assistance"
        )
        if settings.DEBUG:
            msg += f" (DEBUG: {escape(error)})"
        return msg

    def _log_error(self, error: Exception, arxiv_id: str, arxiv_article_id: str | int):
        """
        Log a failed arXiv validation with enough context to investigate it.

        Errors caused by the author's input are logged as warnings; all the others (including arXiv-side errors, such
        as HTTP 429) are logged with their traceback.
        """
        journal = getattr(self.request, "journal", None)
        msg = (
            "arXiv validation failed: journal=%s user=%s arxiv_id=%r article_id=%s existing_article_id=%s: %s"
            " (cause: %s)"
        )
        args = (
            getattr(journal, "code", None),
            self.request.user.pk,
            arxiv_id,
            arxiv_article_id or "new",
            getattr(error, "existing_article_id", None),
            error,
            # the user-facing message hides the technical details, which are in the original exception
            error.__cause__,
        )
        if isinstance(error, ARXIV_USER_ERRORS):
            logger.warning(msg, *args)
        else:
            logger.error(msg, *args, exc_info=error)


class FreeKeywordAutocomplete(KeywordAutocomplete):
    """
    The class is needed to add the group__isnull=True filter to the original KeywordAutocomplete queryset.

    We override the original Janeway URL.
    """

    @property
    def create_field(self):
        """
        Always allow the creation of new keywords.

        :return: The field name to use for creating new keywords.
        """
        return "word"

    def get_queryset(self):
        """
        Return a queryset of available keywords.

        If a search query (`self.q`) is provided, the queryset is filtered
        to include only keywords whose `word` contains the query string
        (case-insensitive) and that are not assigned to any group.

        :return: A Django queryset of `Keyword` objects.
        """
        qs = Keyword.objects.all()
        if self.q:
            qs = qs.filter(word__icontains=self.q, group__isnull=True)
        return qs
