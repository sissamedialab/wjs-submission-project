from core.models import Account
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from submission.models import Article, ArticleAuthorOrder

from ..mixins import AuthorFilteringView, HtmxMixin, StepCheckView
from ..models import ArticleCollaboration, Collaboration
from .forms import AddAuthorForm, AddCollaborationForm, SubmissionStep4Form
from .logic import TableMoveDeleteHandler


class SubmissionStep4View(HtmxMixin, AuthorFilteringView, StepCheckView, UpdateView):
    """Submission step 4."""

    model = Article
    step = 4
    form_class = SubmissionStep4Form

    def setup(self, request, *args, **kwargs):
        """Initialize view and retrieve the article object."""
        super().setup(request, *args, **kwargs)
        self.article = self.get_object()

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_5", kwargs={"article_id": self.object.pk})

    def get_context_data(self, **kwargs):
        """
        Populate view contex with keyword groups.

        :return: Context.
        """
        context = super().get_context_data(**kwargs)
        context["authors_order"] = ArticleAuthorOrder.objects.filter(article=self.article)
        context["is_htmx"] = self.htmx
        context["articles_collaborations"] = ArticleCollaboration.objects.filter(article=self.article)
        return context

    def get_template_names(self):
        """Return template based on HTMX trigger."""
        if self.request.headers.get("Hx-Trigger") in {"id_author_id", "id_correspondence_author"}:
            return ["wjs_submission/step4/selected_authors.html"]
        if self.request.headers.get("Hx-Trigger") == "id_collaboration_id":
            return ["wjs_submission/step4/selected_collaborations.html"]
        if self.request.POST.get("action") in {
            "move_up",
            "move_down",
            "delete",
        }:
            if self.request.headers.get("Hx-Target") == "selected-collaborations-wrapper":
                return ["wjs_submission/step4/selected_collaborations.html"]
            if self.request.headers.get("Hx-Target") == "selected-authors-wrapper":
                return ["wjs_submission/step4/selected_authors.html"]
        return ["wjs_submission/step4/article_form.html"]

    def post(self, request, *args, **kwargs):
        """
        Handle HTMX-driven POST requests for managing article authors and collaborations.

        Depending on the Hx-Trigger header or POST parameters, this method:
        - Adds an author to the article via ArticleAuthorOrder.
        - Updates the article's correspondence author.
        - Adds a collaboration to the article via ArticleCollaboration.
        - Performs move or delete actions for authors or collaborations using TableMoveDeleteHandler.

        :param request: The HTTP request object containing POST data and headers.
        :param args: Additional positional arguments passed to the parent view.
        :param kwargs: Additional keyword arguments passed to the parent view.
        :raises ValidationError: If an unsupported entity type is provided.
        :return: An HTTP response, either the result of `self.get()` for HTMX requests,
             or the parent view's `post` response for non-HTMX requests.
        """
        hx_trigger = request.headers.get("Hx-Trigger")
        if self.htmx:
            if hx_trigger == "id_author_id":
                ArticleAuthorOrder.objects.get_or_create(
                    article=self.article,
                    author_id=request.POST.get("author_id"),
                    defaults={"order": self.article.next_author_sort()},
                )
            elif hx_trigger == "id_correspondence_author":
                self.article.correspondence_author = Account.objects.get(id=request.POST.get("correspondence_author"))
                self.article.save()
            elif hx_trigger == "id_collaboration_id":
                collaboration = Collaboration.objects.get(id=request.POST.get("collaboration_id"))
                ArticleCollaboration.objects.get_or_create(
                    article=self.article,
                    collaboration=collaboration,
                    defaults={
                        "relation": self.request.POST.get("collaboration_relation"),
                        "order": collaboration.next_collaboration_sort(article=self.article),
                    },
                )
            else:
                entity_type = request.POST.get("entity")
                action = request.POST.get("action")
                if entity_type == "author":
                    handler = TableMoveDeleteHandler(
                        model=ArticleAuthorOrder,
                        entity_id=request.POST.get("author_id"),
                        item_field="author",
                        order_field="order",
                        action=action,
                        article=self.article,
                    )
                elif entity_type == "collaboration":
                    handler = TableMoveDeleteHandler(
                        model=ArticleCollaboration,
                        entity_id=request.POST.get("collaboration_id"),
                        item_field="collaboration",
                        order_field="order",
                        action=action,
                        article=self.article,
                    )
                else:
                    msg = f"Unsupported entity type: {entity_type}"
                    raise ValidationError(msg)

                handler.run()

            return self.get(request, *args, **kwargs)

        return super().post(request, *args, **kwargs)


class ModalRenderingMixin(HtmxMixin, AuthorFilteringView, CreateView):
    """
    Common base class for create views handling the creation of objects via modal forms.

    The usage patter is:
    - an HTMX-enabled button calls this view using get to render the form as modal content
    - the modal template contains an HTMX form that target the element containing the list of objects created by the
        view itself
    - on form success, the view renders the template fragment rendering the objects table, and the modal is closed
        from a js snippet in the base template triggered by HX-Trigger event
    - on form error, the view renders the form template and change the target element to the modal contant
        using HX-Retarget header

    Concrete subclasses must:

    - Define model and form_class attributes
    - Implement get_template_names to select the form or the list/table template depending on the value of the
        render_table attribute of the base class
    - Implement get_form_kwargs depending on the form fields.
    """

    render_table = False
    article = None

    def setup(self, request, *args, **kwargs):
        """
        Set up the necessary attributes for handling a specific request.

        This method retrieves an Article instance based on the provided "article_id" in either the
        GET or POST request and delegates further setup to the superclass implementation.

        :param request: The HTTP request object that contains metadata about the request.
        :type request: HttpRequest
        :param args: Positional arguments passed to the setup method.
        :type args: tuple
        :param kwargs: Keyword arguments passed to the setup method.
        :type kwargs: dict
        :return: The return value of the superclass setup method.
        :rtype: Any
        """
        self.article = Article.objects.get(pk=request.GET.get("article_id") or request.POST.get("article_id"))
        return super().setup(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add article_id to context."""
        context = super().get_context_data(**kwargs)
        context["article"] = self.article
        context["article_id"] = self.article.pk
        context["is_htmx"] = self.htmx
        return context

    def form_valid(self, form):
        """Save form and redirect via HTMX."""
        form.save()
        self.render_table = True
        response = self.render_to_response(self.get_context_data())
        response["HX-Trigger"] = "close-active-modal"
        return response

    def form_invalid(self, form):
        """Save form and redirect via HTMX."""
        response = super().form_invalid(form)
        response["HX-Retarget"] = "#htmxModalContent"
        return response


class AddAuthorView(ModalRenderingMixin):
    model = Account
    form_class = AddAuthorForm
    template_name = "wjs_submission/step4/add_author_modal.html"

    def get_template_names(self):
        """
        Determine the appropriate template name to be used based on the object's state.

        If the `render_table` attribute is set to True, the method will return the
        template for rendering selected authors. Otherwise, it will return the
        template for rendering the modal dialog to add an author.

        :return: The string name of the template to be used.
        :rtype: str
        """
        if self.render_table:
            return "wjs_submission/step4/selected_authors.html"
        return "wjs_submission/step4/add_author_modal.html"

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["article_id"] = self.article.pk
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Generate and return the context data for the view.

        This method extends the default context data with additional information
        specific to the view. It includes a filtered queryset containing the
        authors' order related to the article instance.

        :param kwargs: Additional keyword arguments provided by the caller.
        :return: A dictionary representing the context data, including the
            authors' order for the article instance.
        :rtype: dict
        """
        context = super().get_context_data(**kwargs)
        context["authors_order"] = ArticleAuthorOrder.objects.filter(article=self.article)
        return context


class AddCollaborationView(ModalRenderingMixin):
    model = Collaboration
    form_class = AddCollaborationForm

    def get_template_names(self):
        """
        Return the appropriate template name based on the `render_table` attribute.

        If `render_table` is True, the method returns the template name for
        displaying selected collaborations. If `render_table` is False, it returns
        the template name for adding collaborations through a modal.

        :return: Template name corresponding to the render context.
        :rtype: str
        """
        if self.render_table:
            return "wjs_submission/step4/selected_collaborations.html"
        return "wjs_submission/step4/add_collaboration_modal.html"

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["article_id"] = self.article.pk
        kwargs["collaboration_relation"] = self.request.GET.get("collaboration_relation")
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Generate and return the context data for the view.

        This method extends the default context data with additional information
        specific to the view. It includes a filtered queryset containing the
        authors' order related to the article instance.

        :param kwargs: Additional keyword arguments provided by the caller.
        :return: A dictionary representing the context data, including the
            authors' order for the article instance.
        :rtype: dict
        """
        context = super().get_context_data(**kwargs)
        context["articles_collaborations"] = ArticleCollaboration.objects.filter(article=self.article)
        return context
