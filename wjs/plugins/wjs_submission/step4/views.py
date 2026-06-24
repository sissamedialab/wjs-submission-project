from core.models import Account
from django.db.models import QuerySet
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView
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
from .forms import (
    AddAuthorForm,
    AddCollaborationForm,
    AddCollaborationObjectForm,
    AddFrozenAutorObjectForm,
    RevisionStep4Form,
    SubmissionStep4Form,
)
from .logic import TableMoveDeleteHandler, has_author_list_changed


class AuthorsTableRenderingMixin(HtmxMixin):
    """
    Mixin providing functionality for rendering the authors table within an article submission or revision workflow.

    This mixin is designed to be used in views handling article data, such as managing correspondence authors,
    disabled accounts, and author order. It integrates specific context variables required for rendering
    author-related information in associated templates.

    This mixin must be used by views rendering wjs_submission/step4/selected_authors.html (either directly or by
    including it).

    :ivar article: Instance of the `Article` model representing the article associated with the mixin.
    :type article: Article
    :ivar revision_storage: Instance of `RevisionStorage`, used to manage stored revision data for the article.
    :type revision_storage: RevisionStorage
    """

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
        context["step_form"] = (
            SubmissionStep4Form(instance=self.article)
            if not is_revision(self.article)
            else RevisionStep4Form(instance=self.article)
        )
        return context


class CollaborationTableRenderingMixin(HtmxMixin):
    """
    Mixin for rendering collaboration tables in views.

    This mixin provides additional context data for collaboration tables, determining
    if the view is accessed via HTMX, and filtering collaboration objects based on
    the article or revision status. It integrates with HTMX functionality and dynamically
    selects the appropriate collaboration model.

    :ivar htmx: Indicates whether the request originates from HTMX.
    :type htmx: bool
    :ivar revision_storage: Represents the storage for revisions associated with an
        article. Used for filtering collaboration data specifically for revisions.
    :type revision_storage: Any
    :ivar article: Represents the main article object that collaborations are associated
        with when not working with revisions.
    :type article: Any
    """

    article: Article = None
    revision_storage: RevisionStorage = None

    def get_context_data(self, **kwargs):
        """
        Add articles_collaborations to context.

        :param kwargs: Additional context data passed to the method.
        :return: A modified context dictionary containing base context and additional
                 parameters, such as information on whether the request is an HTMX
                 request and relevant article collaboration objects.
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


class SubmissionStep4View(
    CollaborationTableRenderingMixin, AuthorsTableRenderingMixin, AuthorFilteringView, StepCheckView, UpdateView
):
    """
    Handles the rendering and logic for the fourth step in a submission process.

    Manages interactions specific to the fourth step, including form handling,
    template rendering, and context preparation. This view integrates with
    several mixins to enable collaboration management, authors' table rendering,
    and author filtering functionalities. It also manages revisions if they are
    present, adapting its operations accordingly.

    :ivar model: The database model associated with this step.
    :type model: django.db.models.Model
    :ivar step: The step number in the submission process.
    :type step: int
    :ivar form_class: The default form class used for this step.
    :type form_class: django.forms.Form
    :ivar template_name: The path to the template used for rendering this view.
    :type template_name: str
    """

    model = Article
    step = 4
    form_class = SubmissionStep4Form
    template_name = "wjs_submission/step4/article_form.html"

    def get_form_class(self):
        """
        Return the form class to use based on whether this is a revision.

        :return: Form class to use.
        :rtype: django.forms.Form
        """
        if is_revision(self.article):
            return RevisionStep4Form
        return SubmissionStep4Form

    def dispatch(self, request, *args, **kwargs):
        """Retrieve the article object."""
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.article = self.get_object()
        self.revision_storage = (
            RevisionStorage.objects.get(article=self.article) if is_revision(self.article) else None
        )
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_5", kwargs={"article_id": self.object.pk})

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
        self.article = Article.objects.get(pk=kwargs["article_id"])
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


class ReorderAuthorsView(AuthorsTableRenderingMixin, AuthorFilteringView, DetailView):
    """
    Manage the reordering of authors in the submission process.

    This class provides functionality to update the order of authors for a specific
    article during the submission process. It interacts with the appropriate models
    and processes actions sent via POST requests, such as moving or deleting authors
    in the ordering table.

    :ivar model: Specifies the model associated with the view.
    :type model: type[Article]
    :ivar template_name: Specifies the template used to render the view.
    :type template_name: str
    :ivar pk_url_kwarg: The name of the URL parameter used for the primary key of the object.
    :type pk_url_kwarg: str
    :ivar context_object_name: The name of the context variable for the object.
    :type context_object_name: str
    :ivar article: Instance of the `Article` model representing the article associated with the mixin.
    :type article: Article
    :ivar revision_storage: Instance of `RevisionStorage`, used to manage stored revision data for the article.
    :type revision_storage: RevisionStorage
    """

    model: type[Article] = Article
    template_name: str = "wjs_submission/step4/selected_authors.html"
    pk_url_kwarg: str = "article_id"
    context_object_name: str = "article"
    article: Article = None
    revision_storage: RevisionStorage = None

    def post(self, request, *args, **kwargs):
        """Handle POST requests for reordering authors."""
        self.article = self.get_object()
        self.revision_storage = (
            RevisionStorage.objects.get(article=self.article) if is_revision(self.article) else None
        )
        action = request.POST.get("action")
        parent_field = "revision_storage" if self.revision_storage else "article"
        parent_obj = self.revision_storage or self.article
        model = RevisionArticleAuthorOrder if self.revision_storage else FrozenAuthor
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


class SaveCorrespondingAuthorView(AuthorsTableRenderingMixin, AuthorFilteringView, DetailView):
    """
    Save the corresponding author for an article.

    This view allows the user to update the corresponding author for a specific
    article. It handles both the case of normal article updates and revision
    updates by storing the corresponding author in the revision storage if the
    article is under revision.

    :ivar model: The model used for this view.
    :type model: type

    :ivar template_name: The path to the template used for rendering this view.
    :type template_name: str

    :ivar pk_url_kwarg: The name of the URL keyword argument that contains
        the primary key (ID) for the article.
    :type pk_url_kwarg: str

    :ivar context_object_name: The name of the variable in the template context
        that will refer to the article object.
    :type context_object_name: str
    """

    model = Article
    template_name = "wjs_submission/step4/selected_authors.html"
    pk_url_kwarg = "article_id"
    context_object_name = "article"

    def post(self, request, *args, **kwargs):
        """Handle POST requests for reordering authors."""
        self.article = self.get_object()
        if is_revision(self.article):
            self.revision_storage = RevisionStorage.objects.get(article=self.article)
            self.revision_storage.data["correspondence_author"] = request.POST.get("correspondence_author")
            self.revision_storage.save()
        else:
            self.article.correspondence_author = Account.objects.get(id=request.POST.get("correspondence_author"))
            self.article.save()

        return self.get(request, *args, **kwargs)


class AddAuthorView(AuthorsTableRenderingMixin, ModalRenderingMixin):
    """
    Manage adding authors through modal dialog or table rendering.

    This class allows for rendering a modal dialog to add authors or rendering
    a table of selected authors, based on the object's state. It handles the
    retrieval of appropriate templates, the form class to be used, and form
    data processing. The functionality is designed to work seamlessly within
    the submission step of the workflow.

    :ivar model: The model associated with the view.
    :type model: type[Account]
    :ivar form_class: The default form class to use for adding authors.
    :type form_class: type[AddAuthorForm]
    """

    model: type[Account] = Account
    form_class: type[AddAuthorForm] = AddAuthorForm

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
        """
        Determine the form class to be used based on the presence "author_id" parameter in POST data.

        If the "author_id" parameter is present in the POST data of the request, it
        returns the `AddFrozenAutorObjectForm` form class. Otherwise, it defaults
        to the form class specified by the `form_class` attribute of the instance.

        :return: The form class to be used for the current request.
        :rtype: type[Form]
        """
        if self.request.POST.get("author_id"):
            return AddFrozenAutorObjectForm
        return self.form_class

    def get_form_kwargs(self):
        """
        Inject form data from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        self.object = (
            self.model.objects.get(pk=self.request.POST.get("author_id"))
            if self.request.POST.get("author_id")
            else None
        )
        kwargs["article"] = self.article
        kwargs["instance"] = self.object
        kwargs["is_revision"] = is_revision(self.article)
        return kwargs


class AddCollaborationView(CollaborationTableRenderingMixin, ModalRenderingMixin):
    """
    Provide functionality to handle collaboration views in a web application's submission process.

    This class is responsible for rendering collaboration-related interfaces, either as a table or a modal,
    depending on the context. It facilitates the selection and addition of collaborations within a specific
    submission step. The class also handles form configurations dynamically based on the request context.

    :ivar model: The model associated with this view, used to interact with collaboration data.
    :type model: type[Collaboration]
    :ivar form_class: The default form class for adding collaborations.
    :type form_class: type[AddCollaborationForm]
    """

    model: type[Collaboration] = Collaboration
    form_class: type[AddCollaborationForm] = AddCollaborationForm

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

    def get_form_class(self):
        """
        Determine the form class to be used based on the presence "collaboration_id" parameter in POST data.

        If the "author_id" parameter is present in the POST data of the request, it
        returns the `AddCollaborationObjectForm` form class. Otherwise, it defaults
        to the form class specified by the `form_class` attribute of the instance.

        :return: The selected form class based on the request's POST data.
        :rtype: type[Form]
        """
        if self.request.POST.get("collaboration_id"):
            return AddCollaborationObjectForm
        return self.form_class

    def get_form_kwargs(self):
        """
        Inject form data from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        collaboration_id = self.request.POST.get("collaboration_id")
        collaboration_relation = self.request.POST.get("collaboration_relation") or self.request.GET.get(
            "collaboration_relation"
        )
        self.object = self.model.objects.get(pk=collaboration_id) if collaboration_id else None
        kwargs["user"] = self.request.user
        kwargs["collaboration_relation"] = collaboration_relation
        kwargs["article"] = self.article
        kwargs["instance"] = self.object
        kwargs["is_revision"] = is_revision(self.article)
        return kwargs


class ReorderCollaborationsView(CollaborationTableRenderingMixin, AuthorFilteringView, DetailView):
    """
    View for handling the reordering of collaborations within an article.

    This class-based view inherits from multiple mixins and provides functionality
    to reorder collaborations based on a POST request. It fetches the target article
    and processes the request through a table move/delete handler.

    :ivar model: Django model associated with the view.
    :type model: django.db.models.Model
    :ivar template_name: Path to the HTML template used for rendering the view.
    :type template_name: str
    :ivar pk_url_kwarg: URL keyword argument for the primary key of the article.
    :type pk_url_kwarg: str
    :ivar context_object_name: Context variable name used to refer to the article in the template.
    :type context_object_name: str
    :ivar article: Instance of the `Article` model representing the article associated with the mixin.
    :type article: Article
    :ivar revision_storage: Instance of `RevisionStorage`, used to manage stored revision data for the article.
    :type revision_storage: RevisionStorage
    """

    model: type[Article] = Article
    template_name = "wjs_submission/step4/selected_collaborations.html"
    pk_url_kwarg: str = "article_id"
    context_object_name: str = "article"
    article: Article = None
    revision_storage: RevisionStorage = None

    def post(self, request, *args, **kwargs):
        """
        Handle the POST request to perform actions such as moving or deleting article collaboration entities.

        The action is determined based on the `action` parameter passed in the POST
        request. Collaborations are either associated directly with the article or
        with the revision storage, depending on whether the article is a revision.

        :param request: Django request object containing POST data
        :type request: HttpRequest
        :param args: Additional positional arguments
        :param kwargs: Additional keyword arguments
        :return: HTTP response generated by the `get` method
        :rtype: HttpResponse
        """
        self.article = self.get_object()
        self.revision_storage = (
            RevisionStorage.objects.get(article=self.article) if is_revision(self.article) else None
        )
        action = request.POST.get("action")
        parent_field = "revision_storage" if self.revision_storage else "article"
        parent_obj = self.revision_storage or self.article
        model = RevisionArticleCollaboration if self.revision_storage else ArticleCollaboration
        handler = TableMoveDeleteHandler(
            model=model,
            entity_id=request.POST.get("collaboration_id"),
            item_field="collaboration",
            order_field="order",
            action=action,
            parent_obj=parent_obj,
            parent_field=parent_field,
        )
        handler.run()

        return self.get(request, *args, **kwargs)
