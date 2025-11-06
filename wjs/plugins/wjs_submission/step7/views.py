from django.urls import reverse_lazy
from django.views.generic import UpdateView
from submission.models import Article

from ..access_mode import get_access_mode_configuration
from ..mixins import AuthorFilteringView, StepCheckView
from .forms import SubmissionStep7Form


class SubmissionStep7View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 7
    form_class = SubmissionStep7Form
    template_name = "wjs_submission/step7/article_form.html"

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_8", kwargs={"article_id": self.object.pk})

    def get_object(self, queryset=None):
        """
        Set access_mode_configuration for current article.

        :param queryset: QuerySet to retrieve the object from
        :type queryset: QuerySet
        :return: Retrieved object
        :rtype: Any
        :raises AttributeError: If `get_access_mode_configuration` or `super().get_object` encounters an error
        """
        obj = super().get_object(queryset)
        self.access_mode_configuration = get_access_mode_configuration(self.request.user, obj)
        return obj

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["step"] = self.step
        kwargs["journal"] = self.request.journal
        kwargs["configuration"] = self.access_mode_configuration
        return kwargs
