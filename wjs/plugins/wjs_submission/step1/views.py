from django.urls import reverse_lazy
from django.views.generic import CreateView, RedirectView
from django.views.generic.edit import ProcessFormView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView
from ..workflow import (
    is_revision,
    is_revision_confirm,
    is_revision_full,
    is_revision_metadata,
)
from .forms import RevisionConfirmForm, RevisionFullForm, RevisionMetadataForm, SubmissionStep1Form


class SubmissionStep1RedirectView(AuthorFilteringView, RedirectView):
    def get_redirect_url(self, *args, **kwargs):  # noqa: PLR6301
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_1", kwargs={"article_id": kwargs["article_id"]})


class SubmissionStep1View(AuthorFilteringView, StepCheckView, CreateView):
    model = Article
    template_name = "wjs_submission/step1/article_form.html"
    form_class = SubmissionStep1Form
    step = 1

    def get_form_class(self):
        """
        Return the form class to use based on whether this is a revision.

        :return: Form class to use.
        :rtype: django.forms.Form
        """
        if is_revision_confirm(self.object):
            return RevisionConfirmForm
        if is_revision_metadata(self.object):
            return RevisionMetadataForm
        if is_revision_full(self.object):
            return RevisionFullForm

        return SubmissionStep1Form

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_2", kwargs={"article_id": self.object.pk})

    def get_object(self, queryset=None) -> Article | None:
        """
        Fetch and return a specific `Article` object based on the provided queryset and request parameters.

        Checks for 'arxiv_article_id' in POST data or `article_id`
        or `arxiv_article_id` in the URL parameters. If appropriate parameters are
        provided, the object is retrieved. Returns `None` otherwise.

        :param queryset: Optional queryset to filter the objects
        :type queryset: Optional[QuerySet]
        :return: The fetched `Article` object if one is found, otherwise `None`
        :rtype: Article | None
        :raises: AttributeError if an attribute access fails
        """
        if self.request.POST.get("arxiv_article_id"):
            self.kwargs["article_id"] = self.request.POST["arxiv_article_id"]
        if self.kwargs.get("article_id") or self.kwargs.get("arxiv_article_id"):
            return super().get_object(queryset)
        return None

    def get(self, request, *args, **kwargs):
        """
        Handle GET request for processing a form and retrieving an object.

        It tries to retrieve an object based on the provided `article_id` URL parameter, effectively transforming
        the view into an Update view. If no object is found, it behaves as a Create view.

        :param request: The HTTP request object.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: The HTTP response returned by the process form view.
        """
        # As we bypass CreateView.get method and we call superclass ProcessFormView
        # we also skip StepCheckView.get and we must call _verify_step explicitly
        # This is not required when using UpdateView base class as we can call super().post in this case
        if skip := self._verify_step(request, *args, **kwargs):
            return skip
        self.object = self.get_object()
        # Bypassing the CreateView get method and using its superclass one because we want to set self.object,
        # if possible and CreateView would reset it
        return ProcessFormView.get(self, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handle POST request for processing a form and retrieving an object.

        It tries to retrieve an object based on the provided `article_id` URL parameter, effectively transforming
        the view into an Update view. If no object is found, it behaves as a Create view.

        :param request: The HTTP request object.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: The HTTP response returned by the process form view.
        """
        # As we bypass CreateView.post method and we call superclass ProcessFormView
        # we also skip StepCheckView.post and we must call _verify_step explicitly
        # This is not required when using UpdateView base class as we can call super().post in this case
        if skip := self._verify_step(request, *args, **kwargs):
            return skip
        self.object = self.get_object()
        # Bypassing the CreateView get method and using its superclass one because we want to set self.object,
        # if possible and CreateView would reset it
        return ProcessFormView.post(self, request, *args, **kwargs)

    def get_form_kwargs(self):
        """
        Inject journal and user into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["journal"] = self.request.journal
        kwargs["user"] = self.request.user
        kwargs["step"] = self.step
        kwargs["request"] = self.request
        return kwargs

    def get_initial(self):
        """
        Load ArXiv ID from article identifiers and inject in initial form data.

        If no identifier is found, the initial form data is not modified.

        :return: Updated initial data with the 'arxiv_article_id' key if applicable.
        :rtype: dict
        """
        initial = super().get_initial()
        if self.object:
            arxiv_identifier = self.object.identifiers.filter(id_type="arxiv").first()
            if arxiv_identifier:
                initial["arxiv_id"] = arxiv_identifier.identifier
            initial["arxiv_article_id"] = self.object.pk
        return initial

    def get_context_data(self, **kwargs):
        """Add the is_revision flag to the template context."""
        context = super().get_context_data(**kwargs)
        context["is_revision"] = is_revision(self.object)
        return context
