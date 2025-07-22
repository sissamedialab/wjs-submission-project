from django.urls import reverse_lazy
from django.views.generic import CreateView
from events import logic as events_logic
from submission.models import Article

from ..mixins import StepCheckView
from .forms import SubmissionStep1Form


# FIXME: Restrict to staff users
class SubmissionStep1View(StepCheckView, CreateView):
    model = Article
    template_name = "wjs_submission/step1/article_form.html"
    form_class = SubmissionStep1Form
    step = 1

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_2", kwargs={"article_id": self.object.pk})

    def get_form_kwargs(self):
        """
        Inject journal and user into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["journal"] = self.request.journal
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        Raise Janeway's ON_ARTICLE_SUBMISSION_START event on initial submission step to trigger further actions.

        :param form: Form object.
        :return: Response object.
        """
        response = super().form_valid(form)
        events_logic.Events.raise_event(
            events_logic.Events.ON_ARTICLE_SUBMISSION_START,
            request=self.request,
            article=self.object,
        )
        return response
