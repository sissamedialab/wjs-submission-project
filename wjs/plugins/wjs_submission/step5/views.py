from django.urls import reverse_lazy
from django.views.generic import UpdateView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView
from ..workflow import is_revision
from .forms import RevisionStep5Form, SubmissionStep5Form


class SubmissionStep5View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 5
    form_class = SubmissionStep5Form
    template_name = "wjs_submission/step5/article_form.html"

    def get_form_class(self):
        """
        Return the form class to use based on whether this is a revision.

        :return: Form class to use.
        :rtype: django.forms.Form
        """
        if is_revision(self.object):
            return RevisionStep5Form
        return SubmissionStep5Form

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_6", kwargs={"article_id": self.object.pk})

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["step"] = self.step
        kwargs["journal"] = self.request.journal
        return kwargs

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        self.object = form.save(request=self.request)
        return super().form_valid(form)
