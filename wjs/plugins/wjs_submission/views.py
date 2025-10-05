from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, RedirectView, TemplateView
from submission.models import Article, Keyword
from submission.views import KeywordAutocomplete

from .arxiv import ArXivToWjsArticle
from .mixins import AuthorFilteringView, HtmxMixin
from .workflow import STEPS


class Manager(UserPassesTestMixin, TemplateView):
    """Plugin manager page. Just an index."""

    template_name = "wjs_submission/index.html"

    def test_func(self):
        """Verify that only staff can access."""
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)


class RedirectToComplete(AuthorFilteringView, DetailView):
    """Redirect to the article submission complete page."""

    model = Article
    pk_url_kwarg = "article_id"

    def get_redirect_url(self, *args, **kwargs):
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
        step = STEPS.get(article.current_step)

        return step.get_next_step(article)


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
        service = ArXivToWjsArticle(arxiv_id=arxiv_id, journal=self.request.journal, user=self.request.user)
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
            return JsonResponse({"status": "error", "message": f"Error: {e}"})


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
