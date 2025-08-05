from django.views.generic import UpdateView

from ..mixins import AuthorFilteringView, StepCheckView


class SubmissionStep2(AuthorFilteringView, StepCheckView, UpdateView):
    """Submission step 2."""

    step = 2
    fields = ("projected_issue",)
    template_name = "wjs_submission/step2/article_form.html"
