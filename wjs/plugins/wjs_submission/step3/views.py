from django.urls import reverse_lazy
from django.views.generic import UpdateView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView


class SubmissionStep3View(AuthorFilteringView, StepCheckView, UpdateView):
    """Submission step 2."""

    model = Article
    step = 3
    fields = ("stage",)
    template_name = "wjs_submission/step3/article_form.html"

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_3", kwargs={"article_id": self.object.pk})
