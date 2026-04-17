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

    def get_initial(self):
        """
        Return form initial data with additional keys populated using submission data from the underlying object.

        :return: A dictionary containing initial form data with additional submission data
                 keys and their corresponding values.
        :rtype: dict
        :raises AttributeError: If the `submission_data` attribute is missing from the `object`.
        """
        initial = super().get_initial()
        initial["current_step"] = self.step
        if is_revision(self.object):
            revision_storage = self.object.revisionstorage
            initial["title"] = revision_storage.data.get("title")
            initial["abstract"] = revision_storage.data.get("abstract")
            initial["section"] = revision_storage.data.get("section")
            initial["language"] = revision_storage.data.get("language")
        return initial
