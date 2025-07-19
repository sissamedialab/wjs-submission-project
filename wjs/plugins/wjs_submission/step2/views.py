from django.views.generic import UpdateView

from ..mixins import StepCheckView


class SubmissionStep2(StepCheckView, UpdateView):
    """Submission step 2."""

    step = 2
