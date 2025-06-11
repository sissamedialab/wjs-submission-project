from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import TemplateView


class Manager(UserPassesTestMixin, TemplateView):
    """Plugin manager page. Just an index."""

    template_name = "wjs_submission/index.html"

    def test_func(self):
        """Verify that only staff can access."""
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)
