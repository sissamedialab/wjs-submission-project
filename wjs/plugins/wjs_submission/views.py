from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView
from submission.models import Article

from .arxiv import ArXivToWjsArticle
from .mixins import AuthorFilteringView, HtmxMixin


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
