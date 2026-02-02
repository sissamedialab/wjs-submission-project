from django.urls import reverse_lazy
from django.views.generic import UpdateView
from submission.models import Article, ArticleFunding

from ..access_mode import get_access_mode_configuration
from ..mixins import AuthorFilteringView, HtmxMixin, StepCheckView
from ..models import SubmissionArticleFunding
from ..step4 import ModalRenderingMixin
from ..workflow import is_revision
from .forms import AddFundingForm, RevisionStep7Form, SubmissionStep7Form


class SubmissionStep7View(HtmxMixin, AuthorFilteringView, StepCheckView, UpdateView):
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
        context["articles_funding"] = self.object.articlefunding_set.all()
        return context

    def get_template_names(self):
        """Return template based on HTMX trigger."""
        if self.htmx:
            return ["wjs_submission/step7/selected_funding.html"]
        return ["wjs_submission/step7/article_form.html"]

    def post(self, request, *args, **kwargs):
        """
        Handle the HTTP POST request for the view.

        This method processes specific actions based on the `Hx-Target` header in the
        request. If the header and the request data indicate a "delete" action, it deletes
        the corresponding funding record. It also prepares a specific form based on the
        current object, submission step, journal, and access mode configuration for
        rendering the response in an HTMX context. If HTMX is not in use, it falls back
        to the superclass implementation.

        :param request: The HTTP request object.
        :type request: HttpRequest
        :param args: Additional positional arguments.
        :type args: tuple
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: A rendered response context or the superclass' post method's response.
        :rtype: HttpResponse
        """
        hx_target = request.headers.get("Hx-Target")
        if self.htmx:
            self.object = self.get_object()
            if hx_target == "selected-funding-wrapper" and request.POST.get("action") == "delete":
                funding = ArticleFunding.objects.get(pk=request.POST.get("funding_pk"))
                funding.delete()

            form = SubmissionStep7Form(
                instance=self.object,
                step=self.step,
                journal=self.request.journal,
                configuration=self.access_mode_configuration,
            )
            context = self.get_context_data(form=form)
            return self.render_to_response(context)

        return super().post(request, *args, **kwargs)


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
        context["articles_funding"] = self.article.articlefunding_set.all()
        context["funding_pk"] = self.request.GET.get("funding_pk")
        return context

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["article_id"] = self.request.GET.get("article_id") or self.request.POST.get("article_id")
        kwargs["funding_id"] = self.request.GET.get("funding_id")
        kwargs["funding_name"] = self.request.GET.get("funding_name")
        kwargs["funding_country"] = self.request.GET.get("funding_country")

        funding_pk = self.request.GET.get("funding_pk") or self.request.POST.get("funding_pk")
        if funding_pk:
            kwargs["instance"] = SubmissionArticleFunding.objects.select_related("article_funding").get(pk=funding_pk)
        return kwargs

    def form_valid(self, form):
        """Save form and redirect via HTMX."""
        form.save()
        self.render_table = True
        article = Article.objects.get(id=self.request.POST.get("article_id"))
        access_mode_configuration = get_access_mode_configuration(self.request.user, article)
        form = (
            SubmissionStep7Form(
                instance=self.article, journal=self.request.journal, configuration=access_mode_configuration
            )
            if not is_revision(article)
            else RevisionStep7Form(instance=self.article)
        )
        context = self.get_context_data(form=form)
        response = self.render_to_response(context)
        response["HX-Trigger"] = "close-active-modal"
        return response
