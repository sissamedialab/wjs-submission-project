from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse
from django.views.generic import DetailView, TemplateView
from submission.models import Article


class Manager(UserPassesTestMixin, TemplateView):
    """Plugin manager page. Just an index."""

    template_name = "wjs_submission/index.html"

    def test_func(self):
        """Verify that only staff can access."""
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)

    def get(self, request, *args, **kwargs):
        """GET  Da."""
        return super().get(request, *args, **kwargs)


class RedirectToComplete(DetailView):
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
