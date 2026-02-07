from django.urls import reverse_lazy
from django.views.generic import TemplateView, UpdateView
from submission.models import Article

from ..access_mode import get_access_mode_configuration
from ..mixins import AuthorFilteringView, HtmxMixin, StepCheckView
from ..models import SubmissionArticleFunding
from ..step4 import ModalRenderingMixin
from ..workflow import is_revision
from .forms import AddFundingForm, RevisionStep7Form, SubmissionStep7Form


class SubmissionStep7View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 7
    form_class = SubmissionStep7Form
    template_name = "wjs_submission/step7/article_form.html"

    def get_form_class(self):
        """
        Return the form class to use based on whether this is a revision.

        :return: Form class to use.
        :rtype: django.forms.Form
        """
        if is_revision(self.object):
            return RevisionStep7Form
        return SubmissionStep7Form

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

    def get_context_data(self, **kwargs):
        """
        Construct and returns the context data dictionary.

        :param kwargs: Keyword arguments passed to the context data.
        :return: A dictionary containing the context data along with related
            article funding objects.
        """
        context = super().get_context_data(**kwargs)
        context["articles_funding"] = SubmissionArticleFunding.objects.filter(article=self.object)
        return context


class AddFundingView(ModalRenderingMixin):
    model = SubmissionArticleFunding
    form_class = AddFundingForm
    template_name = "wjs_submission/step7/add_funding_modal.html"

    def get_template_names(self):
        """Return template based on HTMX trigger."""
        if self.render_table:
            return "wjs_submission/step7/selected_funding.html"
        return "wjs_submission/step7/add_funding_modal.html"

    def get_context_data(self, **kwargs):
        """Construct and returns the context data dictionary."""
        context = super().get_context_data(**kwargs)
        context["articles_funding"] = SubmissionArticleFunding.objects.filter(article=self.article)
        context["funding_pk"] = self.request.GET.get("funding_pk")
        return context

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        # Parameters passed when adding the funding from dropdown results
        if self.request.GET.get("article_id") and not self.request.GET.get("funding_pk"):
            kwargs["data"] = self.request.GET.copy()
            kwargs["article_id"] = kwargs["data"].pop("article_id")[0]
            if not kwargs["data"]:
                del kwargs["data"]
            funding_pk = self.request.GET.get("funding_pk")
        # Parameters combination when editing an existing funding from the funders table
        elif self.request.GET.get("article_id") and self.request.GET.get("funding_pk"):
            kwargs["article_id"] = self.request.GET.get("article_id")
            funding_pk = self.request.GET.get("funding_pk")
        # We are saving the funding from the modal
        else:
            kwargs["data"] = self.request.POST.copy()
            kwargs["article_id"] = kwargs["data"].pop("article_id")[0]
            funding_pk = self.request.POST.get("funding_pk")
        if funding_pk:
            kwargs["instance"] = SubmissionArticleFunding.objects.get(pk=funding_pk)
        return kwargs

    def form_valid(self, form):
        """Save form and redirect via HTMX."""
        form.save()
        self.render_table = True
        context = self.get_context_data()
        response = self.render_to_response(context)
        response["HX-Trigger"] = "close-active-modal"
        return response


class DeleteFundingView(HtmxMixin, TemplateView):
    model = SubmissionArticleFunding
    template_name = "wjs_submission/step7/selected_funding.html"

    def get_context_data(self, **kwargs):
        """Construct and returns the context data dictionary."""
        context = super().get_context_data(**kwargs)
        context["articles_funding"] = SubmissionArticleFunding.objects.filter(article=self.article)
        context["funding_pk"] = self.request.GET.get("funding_pk")
        return context

    def get_object(self, queryset=None):
        """
        Retrieve an object from the specified queryset based on a primary key obtained from the request.

        :param queryset: Optional; a queryset to search for the object. Defaults to None.
        :type queryset: QuerySet, optional
        :return: The object retrieved from the queryset matching the primary key in the request.
        :rtype: SubmissionArticleFunding
        :raises SubmissionArticleFunding.DoesNotExist: If no object with specified primary key exists in the queryset.
        """
        return SubmissionArticleFunding.objects.get(pk=self.request.POST.get("funding_pk"))

    def post(self, request, *args, **kwargs):
        """
        Delete the object associated with the request and render the response with the updated context.

        :param request: HttpRequest object containing metadata about the request.
        :type request: HttpRequest
        :param args: Positional arguments passed to the method.
        :type args: tuple
        :param kwargs: Keyword arguments passed to the method.
        :type kwargs: dict
        :return: HttpResponse with the rendered context after object deletion.
        :raises: AttributeError if the object to be deleted is not found.
        """
        self.object = self.get_object()
        self.article = self.object.article
        self.object.delete()
        return self.render_to_response(self.get_context_data())
