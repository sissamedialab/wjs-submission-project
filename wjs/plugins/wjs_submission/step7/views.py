from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.views.generic import TemplateView, UpdateView
from submission.models import Article

from ..access_mode import AccessModeConfiguration, get_access_mode_configuration
from ..mixins import AuthorFilteringView, HtmxMixin, StepCheckView
from ..models import (
    RevisionSubmissionArticleFunding,
    SubmissionArticleFunding,
)
from ..step4 import ModalRenderingMixin
from ..workflow import is_revision
from .forms import (
    AddFundingForm,
    RevisionAddFundingForm,
    RevisionStep7Form,
    SubmissionStep7Form,
)


def get_article_fundings(article):
    if is_revision(article):
        return RevisionSubmissionArticleFunding.objects.filter(revision_storage__article=article)
    return SubmissionArticleFunding.objects.filter(article=article)


class SubmissionStep7View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 7
    form_class = SubmissionStep7Form
    template_name = "wjs_submission/step7/article_form.html"
    access_mode_configuration: AccessModeConfiguration | None

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
        context["articles_funding"] = get_article_fundings(self.object)
        context["is_revision"] = is_revision(self.object)
        return context


class AddFundingView(ModalRenderingMixin):
    template_name = "wjs_submission/step7/add_funding_modal.html"
    object = None
    is_revision = False

    @property
    def model(self):
        """
        Return the model class based on the state of the object.

        :returns: The corresponding model class.
        :rtype: Type
        :raises AttributeError: If the object's attributes are improperly configured.
        """
        if self.is_revision:
            return RevisionSubmissionArticleFunding
        return SubmissionArticleFunding

    def get_form_class(self):
        """
        Determine and return the appropriate form class based on the revision state of the article.

        :return: The form class to use for handling funding data.
        :rtype: type[AddFundingForm] | type[RevisionAddFundingForm]
        :raises AttributeError: If the attribute `article` is not defined or accessible.
        """
        if is_revision(self.article):
            return RevisionAddFundingForm
        return AddFundingForm

    def get_template_names(self):
        """Return template based on HTMX trigger."""
        if self.render_table:
            return "wjs_submission/step7/selected_funding.html"
        return "wjs_submission/step7/add_funding_modal.html"

    def get_context_data(self, **kwargs):
        """Construct and returns the context data dictionary."""
        context = super().get_context_data(**kwargs)
        context["articles_funding"] = get_article_fundings(self.article)
        context["funding_pk"] = self.request.GET.get("funding_pk")
        if self.is_revision:
            context["add_funding_url"] = reverse("add-funding-revision")
            context["delete_funding_url"] = reverse("delete-funding-revision")
        else:
            context["add_funding_url"] = reverse("add-funding")
            context["delete_funding_url"] = reverse("delete-funding")
        return context

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        funding_pk = None
        kwargs = super().get_form_kwargs()
        if self.request.method == "POST":
            kwargs["data"] = self.request.POST
            funding_pk = self.request.POST.get("funding_pk")
        elif self.request.method == "GET":
            funding_pk = self.request.GET.get("funding_pk")
            if not funding_pk and self.request.GET.get("fundref_id"):
                kwargs["data"] = self.request.GET
        if funding_pk:
            self.object = self.model.objects.get(pk=funding_pk)
        kwargs["article"] = self.article
        kwargs["instance"] = self.object
        return kwargs

    def get(self, *args, **kwargs):
        """
        Handle GET request and add custom trigger to trigger opening of the modal.

        :param args: Positional arguments passed to the parent `get` method
        :type args: tuple
        :param kwargs: Keyword arguments passed to the parent `get` method
        :type kwargs: dict
        :return: Response object with the added HX-Trigger header
        :rtype: dict
        """
        response = super().get(*args, **kwargs)
        response["HX-Trigger"] = "open-active-modal"
        return response

    def form_valid(self, form):
        """
        Save form and add custom trigger to trigger opening of the modal.

        :param form:
        :return:
        """
        form.save()
        self.render_table = True
        context = self.get_context_data()
        response = self.render_to_response(context)
        response["HX-Trigger"] = "close-active-modal"
        return response


class DeleteFundingView(HtmxMixin, TemplateView):
    template_name = "wjs_submission/step7/selected_funding.html"
    is_revision = False

    @property
    def model(self):
        """
        Return the appropriate model based on whether the instance represents a revision.

        :raises AttributeError: If any required attributes are not properly set.
        :return: Returns `RevisionSubmissionArticleFunding` if the instance represents
            a revision. Otherwise, returns `SubmissionArticleFunding`.
        :rtype: type
        """
        if is_revision(self.article):
            return RevisionSubmissionArticleFunding
        return SubmissionArticleFunding

    @cached_property
    def article(self):
        """
        Retrieve the Article object based on the article_id provided in the POST request.

        :return: The Article object corresponding to the provided article_id
        :rtype: Article
        :raises Article.DoesNotExist: If no Article is found with the given article_id
        """
        return Article.objects.get(pk=self.request.POST.get("article_id"))

    def get_context_data(self, **kwargs):
        """Construct and returns the context data dictionary."""
        context = super().get_context_data(**kwargs)
        context["is_htmx"] = self.htmx
        context["article"] = self.article
        context["funding_pk"] = self.request.GET.get("funding_pk")
        if is_revision(self.article):
            context["articles_funding"] = self.model.objects.filter(revision_storage__article=self.article)
            context["add_funding_url"] = reverse("add-funding-revision")
            context["delete_funding_url"] = reverse("delete-funding-revision")
        else:
            context["articles_funding"] = self.model.objects.filter(article=self.article)
            context["add_funding_url"] = reverse("add-funding")
            context["delete_funding_url"] = reverse("delete-funding")
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
        return self.model.objects.get(pk=self.request.POST.get("funding_pk"))

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
        self.object.delete()
        return self.render_to_response(self.get_context_data())
