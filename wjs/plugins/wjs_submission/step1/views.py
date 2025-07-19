from django.views.generic import CreateView

from ..mixins import StepCheckView
from .forms import SubmissionStep1Form


class SubmissionStep1(StepCheckView, CreateView):
    """Submission step 1."""

    form_class = SubmissionStep1Form
    step = 1
    template_name = "wjs_submission/step1/article_form.html"
