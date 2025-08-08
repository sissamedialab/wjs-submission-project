from django.urls import reverse_lazy
from django.views.generic import UpdateView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView
from .forms import SubmissionStep2Form


class SubmissionStep2View(AuthorFilteringView, StepCheckView, UpdateView):
    """Submission step 2."""

    model = Article
    step = 2
    form_class = SubmissionStep2Form
    template_name = "wjs_submission/step2/article_form.html"

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_3", kwargs={"article_id": self.object.pk})

    def get_form_kwargs(self):
        """
        Inject journal and user into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["journal"] = self.request.journal
        kwargs["user"] = self.request.user
        kwargs["request"] = self.request
        return kwargs
