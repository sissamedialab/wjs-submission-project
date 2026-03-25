from core.models import Account
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from submission.models import Article, FrozenAuthor

from ..account_validation import (
    is_user_eligible_for_correspondence_author,
    verify_profile_completion,
)
from ..mixins import AuthorFilteringView, HtmxMixin, StepCheckView
from ..models import (
    ArticleCollaboration,
    Collaboration,
    RevisionArticleAuthorOrder,
    RevisionArticleCollaboration,
    RevisionStorage,
)
from ..workflow import is_revision
from .forms import AddAuthorForm, AddCollaborationForm, AddFrozenAutorForm, RevisionStep4Form, SubmissionStep4Form
from .logic import TableMoveDeleteHandler, has_author_list_changed


class AuthorsTableRenderingMixin(HtmxMixin):
    article: Article = None
    revision_storage: RevisionStorage = None

    @staticmethod
    def _get_correspondence_author_list(article: Article) -> QuerySet:
        """
        Retrieve the list of correspondence authors associated with the given article.

        :param article: The article instance.
        :type article: Article
        :return: Queryset of Account objects representing the correspondence authors.
        :rtype: QuerySet
        :raises: None
        """
        return article.author_accounts.all()

    @staticmethod
    def _get_disabled_accounts(article: Article, authors: QuerySet) -> set:
        """
        Identify and return the IDs of disabled accounts based on the given criteria.

        :param article: The article instance.
        :type article: Article
        :param authors: A QuerySet of author objects to evaluate
        :type authors: QuerySet
        :return: A set containing the IDs of authors whose accounts are considered disabled
        :rtype: set
        """
        return {
            author.pk for author in authors if not is_user_eligible_for_correspondence_author(article.journal, author)
        }

    def get_context_data(self, **kwargs):
        """
        Populate view contex with keyword groups.

        :return: Context.
        """
        context = super().get_context_data(**kwargs)
        authors_list = self._get_correspondence_author_list(self.article)
        disabled_accounts = self._get_disabled_accounts(self.article, authors_list)
        # The following error can be used by the view's template in order to
        # indicate required/desirable actions to the operator:
        context["correspondence_author_error"] = verify_profile_completion(
            journal=self.article.journal,
            disabled_users=disabled_accounts,
            user=self.article.correspondence_author,
            is_owner=self.article.correspondence_author == self.article.owner,
        )
        context["disabled_accounts"] = disabled_accounts
        context["is_htmx"] = self.htmx
        fk_field = (
            {"revision_storage": self.revision_storage} if is_revision(self.article) else {"article": self.article}
        )
        context["authors_order"] = (
            RevisionArticleAuthorOrder if is_revision(self.article) else FrozenAuthor
        ).objects.filter(**fk_field)
        context["correspondence_author"] = (
            Account.objects.get(pk=self.revision_storage.data["correspondence_author"])
            if is_revision(self.article) and self.revision_storage
            else self.article.correspondence_author
        )
        context["has_author_list_changed"] = is_revision(self.article) and has_author_list_changed(self.article)
        return context


class SubmissionStep4View(AuthorsTableRenderingMixin, AuthorFilteringView, StepCheckView, UpdateView):
    """Submission step 4."""

    model = Article
    step = 4
    form_class = SubmissionStep4Form

    def get_form_class(self):
        """
        Return the form class to use based on whether this is a revision.

        :return: Form class to use.
        :rtype: django.forms.Form
        """
        if is_revision(self.article):
            return RevisionStep4Form
        return SubmissionStep4Form

    def setup(self, request, *args, **kwargs):
        """Initialize view and retrieve the article object."""
        super().setup(request, *args, **kwargs)
        self.article = self.get_object()
        self.revision_storage = None
        if is_revision(self.article):
            self.revision_storage = RevisionStorage.objects.get(article=self.article)

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
        context["is_htmx"] = self.htmx
        fk_field = (
            {"revision_storage": self.revision_storage} if is_revision(self.article) else {"article": self.article}
        )
        context["articles_collaborations"] = (
            RevisionArticleCollaboration if is_revision(self.article) else ArticleCollaboration
        ).objects.filter(**fk_field)
        return context

    def get_form_kwargs(self):
        """
        Inject journal and user into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["step"] = self.step
        if is_revision(self.article):
            kwargs["has_author_list_changed"] = is_revision(self.article) and has_author_list_changed(self.article)
        return kwargs

    def get_initial(self):
        """
        Inject authors_contributions / collaboration_relation data into the form.

        :return: The initial data dictionary with optional values for authors' contributions
                 and collaboration relation.
        :rtype: dict
        :raises Exception: If any issue occurs while accessing the revision storage or fetching
                           editor revision requests.
        """
        initial = super().get_initial()
        if self.revision_storage:
            initial["authors_contributions"] = self.revision_storage.data.get("authors_contributions")
            initial["collaboration_relation"] = self.revision_storage.data.get("collaboration_relation")
        return initial

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

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests and triggers an HX update fragment event if the author list has changed.

        Provides a response enriched with the necessary HX-Trigger header.

        :param request: The HTTP request object containing all HTTP request details.
        :type request: django.http.HttpRequest
        :param args: Positional arguments passed to the handler.
        :type args: list
        :param kwargs: Keyword argument parameters passed to the handler.
        :type kwargs: dict
        :return: The HTTP response object, possibly containing an HX-Trigger header
                 indicating whether the fragment update is required.
        :rtype: django.http.HttpResponse
        """
        response = super().get(request, *args, **kwargs)
        show_fragment = has_author_list_changed(self.article)
        response["HX-Trigger"] = f"update-fragment:{int(show_fragment)}"
        return response

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
            if hx_trigger == "id_correspondence_author":
                if is_revision(self.article):
                    self.revision_storage.data["correspondence_author"] = request.POST.get("correspondence_author")
                    self.revision_storage.save()
                else:
                    self.article.correspondence_author = Account.objects.get(
                        id=request.POST.get("correspondence_author")
                    )
                    self.article.save()
            elif hx_trigger == "id_collaboration_id":
                collaboration = Collaboration.objects.get(id=request.POST.get("collaboration_id"))
                model, fk = (
                    (
                        RevisionArticleCollaboration,
                        {"revision_storage": RevisionStorage.objects.get(article=self.article)},
                    )
                    if is_revision(self.article)
                    else (ArticleCollaboration, {"article": self.article})
                )
                model.objects.get_or_create(
                    **fk,
                    collaboration=collaboration,
                    defaults={
                        "relation": self.request.POST.get("collaboration_relation"),
                        "order": collaboration.next_collaboration_sort(
                            article=self.article, revision=is_revision(self.article)
                        ),
                    },
                )
            else:
                entity_type = request.POST.get("entity")
                action = request.POST.get("action")
                parent_field = "revision_storage" if is_revision(self.article) else "article"
                parent_obj = self.article if not is_revision(self.article) else self.revision_storage
                if entity_type == "collaboration":
                    model = RevisionArticleCollaboration if is_revision(self.article) else ArticleCollaboration
                    handler = TableMoveDeleteHandler(
                        model=model,
                        entity_id=request.POST.get("collaboration_id"),
                        item_field="collaboration",
                        order_field="order",
                        action=action,
                        parent_obj=parent_obj,
                        parent_field=parent_field,
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
    article: Article = None
    revision_storage: RevisionStorage = None

    def setup(self, request, *args, **kwargs):
        """
        Set up the necessary attributes for handling a specific request.

        This method retrieves an Article instance based on the provided "article_id" in either the
        GET or POST request and delegates further setup to the superclass implementation and its RevisionStorage
        (if any) instance.

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
        self.revision_storage = RevisionStorage.objects.filter(article=self.article).first()
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
        form = (
            SubmissionStep4Form(instance=self.article)
            if not is_revision(self.article)
            else RevisionStep4Form(instance=self.article)
        )
        context = self.get_context_data(form=form)
        response = self.render_to_response(context)
        show_fragment = has_author_list_changed(self.article)
        response["HX-Trigger"] = f"close-active-modal,update-fragment:{int(show_fragment)}"
        return response

    def form_invalid(self, form):
        """Save form and redirect via HTMX."""
        response = super().form_invalid(form)
        response["HX-Retarget"] = "#htmxModalContent"
        return response


class ReorderAuthorsView(AuthorsTableRenderingMixin, AuthorFilteringView, UpdateView):
    model = Article
    template_name = "wjs_submission/step4/selected_authors.html"
    pk_url_kwarg = "article_id"
    context_object_name = "article"
    fields = ("correspondence_author",)

    def post(self, request, *args, **kwargs):
        """Handle POST requests for reordering authors."""
        self.article = self.get_object()
        action = request.POST.get("action")
        parent_field = "revision_storage" if is_revision(self.article) else "article"
        parent_obj = self.article if not is_revision(self.article) else self.revision_storage
        model = RevisionArticleAuthorOrder if is_revision(self.article) else FrozenAuthor
        handler = TableMoveDeleteHandler(
            model=model,
            entity_id=request.POST.get("author_id"),
            item_field="author",
            order_field="order",
            action=action,
            parent_obj=parent_obj,
            parent_field=parent_field,
        )
        handler.run()

        return self.get(request, *args, **kwargs)


class SaveCorrespondingAuthorView(AuthorsTableRenderingMixin, AuthorFilteringView, UpdateView):
    model = Article
    template_name = "wjs_submission/step4/selected_authors.html"
    pk_url_kwarg = "article_id"
    context_object_name = "article"
    fields = ("correspondence_author",)

    def post(self, request, *args, **kwargs):
        """Handle POST requests for reordering authors."""
        self.article = self.get_object()
        if is_revision(self.article):
            self.revision_storage.data["correspondence_author"] = request.POST.get("correspondence_author")
            self.revision_storage.save()
        else:
            self.article.correspondence_author = Account.objects.get(id=request.POST.get("correspondence_author"))
            self.article.save()

        return self.get(request, *args, **kwargs)


class AddAuthorView(AuthorsTableRenderingMixin, ModalRenderingMixin):
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

    def get_form_class(self):
        if self.request.POST.get("author_id"):
            return AddFrozenAutorForm
        return self.form_class

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        self.object = (
            Account.objects.get(pk=self.request.POST.get("author_id")) if self.request.POST.get("author_id") else None
        )
        kwargs["article"] = self.article
        kwargs["instance"] = self.object
        kwargs["is_revision"] = is_revision(self.article)
        return kwargs


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
        kwargs["is_revision"] = is_revision(self.article)
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
        fk_field = (
            {"revision_storage": RevisionStorage.objects.get(article=self.article)}
            if is_revision(self.article)
            else {"article": self.article}
        )
        context["articles_collaborations"] = (
            RevisionArticleCollaboration if is_revision(self.article) else ArticleCollaboration
        ).objects.filter(**fk_field)
        return context
