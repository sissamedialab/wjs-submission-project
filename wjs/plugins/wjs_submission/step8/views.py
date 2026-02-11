from django.urls import reverse_lazy
from django.views.generic import UpdateView
from submission.models import Article

from ..access_mode import get_access_mode_configuration
from ..mixins import AuthorFilteringView, StepCheckView
from ..step6.views import get_files
from ..step7.views import get_article_fundings
from ..workflow import is_revision, step_check_access_funding, step_check_select_issue
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

    def _step7_skipped(self) -> bool:
        """
        Determine whether step 7 is skipped based on access funding check.

        :return: True if step 7 is skipped, False otherwise
        :rtype: bool
        """
        return not step_check_access_funding(self.object.journal, self.object, self.request.user)

    def _process_step7(self):
        """
        Assign the access mode configuration to the object's submission data if the object is not a revision.

        If the object is a revision, the access mode is already set in the submission data and no further action
        is required.

        :param kwargs: Additional keyword arguments
        :raises Exception: If exceptions occur during the process of fetching or saving the configuration
        """
        configuration = get_access_mode_configuration(self.request.user, self.object)
        if not is_revision(self.object) and self._step7_skipped and configuration.access_mode:
            self.object.submission_data.access_mode = configuration.access_mode
            self.object.submission_data.save()

    def get_form_kwargs(self):
        """
        Inject necessary data into the form.

        Process step 7 if skipped due to single access mode and funding is not enabled.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["step"] = self.step
        self._process_step7()
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

        context["articles_fundings"] = get_article_fundings(self.object)
        # Include files (manuscript_files, data_figure_files, etc.)
        context.update(get_files(article=self.object))

        return context
