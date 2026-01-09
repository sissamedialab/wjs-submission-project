from django.urls import reverse_lazy
from django.views.generic import UpdateView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView
from .forms import RevisionForm


class SubmissionStep8View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 8
    template_name = "wjs_submission/step8/article_form.html"
    fields = ("title",)

    def get_success_url(self):
        """Go to the status page."""
        return reverse_lazy("wjs_article_details", args=(self.object.articleworkflow.pk,))

    def get_form_class(self):  # noqa: PLR6301
        """Return the revision-form."""
        return RevisionForm

    def get_form_kwargs(self):
        """Add the request to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs
