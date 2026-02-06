from django.urls import reverse_lazy
from django.views.generic import UpdateView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView
from ..workflow import is_revision, step_check_select_issue
from .forms import RevisionForm, SubmissionStep8Form


class SubmissionStep8View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 8
    template_name = "wjs_submission/step8/article_form.html"

    def get_success_url(self):
        """
        Redirect to the status page through wjs_submission_0.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_0", kwargs={"article_id": self.object.pk})

    def get_form_class(self):
        """Return the revision-form."""
        if is_revision(self.object):
            return RevisionForm
        return SubmissionStep8Form

    def get_form_kwargs(self):
        """
        Inject necessary data into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["step"] = self.step
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Inject necessary data into the context.

        :return: Context data.
        """
        context = super().get_context_data(**kwargs)
        if arxiv_identifier := context["article"].identifiers.filter(id_type="arxiv").first():
            context["arxiv_id"] = arxiv_identifier.identifier
        context["show_issue"] = step_check_select_issue(self.object.journal, user=self.request.user)
        context["is_revision"] = is_revision(self.object)
        return context
