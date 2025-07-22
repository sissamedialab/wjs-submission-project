from django.views.generic import UpdateView

from ..mixins import StepCheckView


# FIXME: Restrict to staff users
class SubmissionStep2(StepCheckView, UpdateView):
    """Submission step 2."""

    step = 2
