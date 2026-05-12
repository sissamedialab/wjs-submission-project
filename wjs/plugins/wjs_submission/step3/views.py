from django.urls import reverse_lazy
from django.utils.module_loading import import_string
from django.views.generic import UpdateView
from plugins.wjs_submission.keywords import get_keyword_range_by_journal
from submission.models import Article

from .. import settings as submission_settings
from ..mixins import AuthorFilteringView, StepCheckView
from .forms import SubmissionStep3Form


class SubmissionStep3View(AuthorFilteringView, StepCheckView, UpdateView):
    """Submission step 3."""

    model = Article
    step = 3
    form_class = SubmissionStep3Form
    template_name = "wjs_submission/step3/article_form.html"

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_4", kwargs={"article_id": self.object.pk})

    def get_context_data(self, **kwargs):
        """
        Populate view contex with keyword groups.

        :return: Context.
        """
        context = super().get_context_data(**kwargs)
        keyword_range = get_keyword_range_by_journal(self.request.journal)
        arxiv_category = getattr(getattr(self.get_object(), "submission_data", None), "arxiv_category", None)

        filter_path = submission_settings.KEYWORD_FILTERS.get(
            self.request.journal, submission_settings.KEYWORD_FILTERS.get(None)
        )
        filter_fn = import_string(filter_path)
        context["keywords_list"] = filter_fn(self.request.journal, arxiv_category)
        context["keywords_count"] = keyword_range
        context["ENABLE_FREE_KEYWORD"] = submission_settings.ENABLE_FREE_KEYWORD
        return context

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["form_data"] = self.request.POST
        kwargs["instance"] = self.get_object()
        kwargs["step"] = self.step
        return kwargs
