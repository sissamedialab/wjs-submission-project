import logging

from core import models as core_models
from django.db.models import QuerySet
from django.urls import reverse_lazy
from django.views.generic import DeleteView, DetailView, FormView, UpdateView
from submission.models import Article
from utils.setting_handler import get_setting

from ..mixins import AuthorFilteringView, HtmxMixin, StepCheckView
from ..models import RevisionStorage
from ..workflow import get_feedback_ws_url, is_revision, is_revision_confirm, is_revision_full, is_revision_metadata
from .forms import RevisionStep6Form, RevisionUploadArticleForm, SubmissionStep6Form, UploadArticleForm

logger = logging.getLogger(__name__)


class TableRenderingContext:
    @property
    def _article(self) -> Article:
        """Retrieve article object."""
        return Article.objects.get(pk=self.kwargs["article_id"])

    def get_context_data(self, **kwargs):
        """
        Add to context the files list & co.

        The returned context is suitable both for the main template (article_form.html) and the single files-tables
        templates (files_table.html).
        Also, this method knows both about normal submissions and revisions and gets the files from the Article or the
        RevisionStorage accordingly.

        :param kwargs: Additional keyword arguments passed to the method.
        :return: The modified context dictionary with additional article files and related attributes.
        :rtype: dict
        """
        context = super().get_context_data(**kwargs)
        context["article"] = self._article
        file_type = self.kwargs.get("file_type")

        # TODO: refactor (maybe?)
        #       collect the files in the outer "if"
        #       in the inner "if", only add the files to the context with the correct keys

        # When working on a normal submission, we take the files from the article,
        # when working on a revision, we take the files from the revision storage.
        if not is_revision(self._article):
            if file_type:
                # When "file_type" is defined, it means that we are Working on a single table:
                # we must provide context for the files_table.html template.
                context["button_name"] = f"trigger_{file_type}"
                context["file_type"] = file_type

                if file_type == "manuscript":
                    context["show_conversion"] = True
                    context["files_list"] = (
                        self._article.manuscript_files
                        if self._article.manuscript_files.exists()
                        else self._article.source_files
                    )
                    context["failed_conversion_log"] = core_models.File.objects.filter(
                        article_id=self._article.pk, label="Failed conversion log ConvertManuscriptToPdf"
                    ).first()
                elif file_type == "data":
                    context["files_list"] = self._article.data_figure_files
                elif file_type == "administrative":
                    context["files_list"] = self._article.submission_data.administrative_files
            else:
                # Working on the main view; provide context for all tables in article_form.html
                context["manuscript_files"] = (
                    self._article.manuscript_files
                    if self._article.manuscript_files.exists()
                    else self._article.source_files
                )
                context["data_figure_files"] = self._article.data_figure_files
                context["administrative_files"] = self._article.submission_data.administrative_files
        else:
            # Revision: get files from RevisionStorage
            revision_storage = RevisionStorage.objects.get(article=self._article)

            if file_type:
                # Working on a single table; provide context for files_table.html
                context["button_name"] = f"trigger_{file_type}"
                context["file_type"] = file_type

                if file_type == "manuscript":
                    context["show_conversion"] = True
                    if file_id := revision_storage.data["manuscript_files"]:
                        context["files_list"] = core_models.File.objects.filter(id=file_id)
                    elif file_id := revision_storage.data["source_files"]:
                        # Show source file if manuscript conversion failed
                        context["files_list"] = core_models.File.objects.filter(id=file_id)
                    else:
                        context["files_list"] = core_models.File.objects.none()

                    context["failed_conversion_log"] = core_models.File.objects.filter(
                        article_id=self._article.pk, label="Failed conversion log ConvertManuscriptToPdf"
                    ).first()
                elif file_type == "data":
                    context["files_list"] = core_models.File.objects.filter(
                        id__in=revision_storage.data["data_figure_files"],
                    )
                elif file_type == "administrative":
                    context["files_list"] = core_models.File.objects.filter(
                        id__in=revision_storage.data["administrative_files"],
                    )
            else:
                # Working on the main view; provide context for all tables in article_form.html
                if file_id := revision_storage.data["manuscript_files"]:
                    context["manuscript_files"] = core_models.File.objects.filter(id=file_id)
                elif file_id := revision_storage.data["source_files"]:
                    # Show source file if manuscript conversion failed
                    context["manuscript_files"] = core_models.File.objects.filter(id=file_id)
                else:
                    context["manuscript_files"] = core_models.File.objects.none()

                # TODO specs#2330: review data-figure vs supplementary vs administrative files relation
                context["supplementary_files"] = core_models.File.objects.filter(
                    id__in=revision_storage.data["supplementary_files"],
                )
                context["data_figure_files"] = core_models.File.objects.filter(
                    id__in=revision_storage.data["data_figure_files"],
                )
                context["administrative_files"] = core_models.File.objects.filter(
                    id__in=revision_storage.data["administrative_files"],
                )

        return context


class SubmissionStep6View(AuthorFilteringView, StepCheckView, TableRenderingContext, UpdateView):
    model = Article
    step = 6
    form_class = SubmissionStep6Form
    template_name = "wjs_submission/step6/article_form.html"

    def get_form_class(self):
        """
        Return the form class to use based on whether this is a revision.

        :return: Form class to use.
        :rtype: django.forms.Form
        """
        if is_revision_confirm(self.object):
            raise ValueError("Revisions with flow-type confirm-previous-version should never touch the files!")
        if is_revision_metadata(self.object):
            raise ValueError("Revisions with flow-type metadata-change should never touch the files!")
        if is_revision_full(self.object):
            return RevisionStep6Form

        return SubmissionStep6Form

    def get_success_url(self):
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_7", kwargs={"article_id": self.object.pk})

    def get_form_kwargs(self):
        """
        Inject form date from POST request into the form.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["step"] = self.step
        kwargs["journal"] = self.request.journal
        return kwargs

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
        initial["das"] = self.object.submission_data.das
        initial["das_url"] = self.object.submission_data.das_url
        initial["cas"] = self.object.submission_data.cas
        initial["cas_url"] = self.object.submission_data.cas_url
        return initial

    def get_context_data(self, **kwargs):
        """
        Add WebSocket URL for feedback to the template context.

        This method extends the default context data to include a
        WebSocket URL that the template can use to connect to the
        feedback channel for this specific article and user.

        Args:
            **kwargs: Arbitrary keyword arguments passed to the base context.

        Returns:
            dict: Context dictionary extended with "feedback_ws_url".

        """
        context = super().get_context_data(**kwargs)
        context["feedback_ws_url"] = get_feedback_ws_url(self.request, self.object.pk, self.request.user.pk)
        return context


class RenderSubmissionFile(HtmxMixin, AuthorFilteringView, TableRenderingContext, DetailView):
    model = Article
    pk_url_kwarg = "article_id"
    template_name = "wjs_submission/step6/includes/files_table.html"
    context_object_name = "article"


class DeleteSubmissionFile(HtmxMixin, AuthorFilteringView, TableRenderingContext, DeleteView):
    model = core_models.File
    pk_url_kwarg = "file_id"
    template_name = "wjs_submission/step6/includes/files_table.html"

    def get_queryset(self) -> QuerySet:
        """
        Filter and retrieve query set for the specified article ID.

        :return: Filtered QuerySet containing objects matching the given article ID.
        :rtype: QuerySet

        :raises: KeyError if "article_id" is not found in `kwargs`.
        """
        return self.model.objects.filter(article_id=self.kwargs["article_id"])

    def _delete_files(self):
        """
        Delete the selected file.

        If file to delete is a source file, manuscript files are cleared.
        Same if the file is a manuscript file, source files are cleared.
        """
        if not is_revision(self._article):
            if self.object in self._article.source_files.all():
                for f in self._article.manuscript_files.all():
                    f.delete()
            if self.object in self._article.manuscript_files.all():
                for f in self._article.source_files.all():
                    f.delete()
            self.object.delete()
            self._article.refresh_from_db()
        else:
            revision_storage = RevisionStorage.objects.get(article=self._article)
            # HELP: refactor the following to delete the file and its "reference" inside a `with transaction.atomic():`
            file_type = self.kwargs["file_type"]
            if file_type == "manuscript":
                self.object.delete()
                revision_storage.data["manuscript_files"] = ""
                if source_file_id := revision_storage.data["source_files"]:
                    core_models.File.objects.get(id=source_file_id).delete()
                    revision_storage.data["source_files"] = ""

            elif file_type == "source_files":  # HELP: sort-of "not implemented"
                self.object.delete()
                revision_storage.data["source_files"] = ""
                if manuscript_file_id := revision_storage.data["manuscript_files"]:
                    core_models.File.objects.get(id=manuscript_file_id).delete()
                    revision_storage.data["manuscript_files"] = ""

            elif file_type == "data":
                revision_storage.data["data_figure_files"].remove(self.object.id)
                self.object.delete()

            elif file_type == "supplementary_files":
                # TODO specs#2330: ⚠ supplementary files are not core.File, but core.SupplementaryFiles!
                revision_storage.data["supplementary_files"].remove(self.object.id)
                self.object.delete()

            elif file_type == "administrative":
                revision_storage.data["administrative_files"].remove(self.object.id)
                self.object.delete()

            else:
                logger.error(f"""Trying to delete unexpected file type "{file_type}" for article {self._article.id}""")

            revision_storage.save()

    def form_valid(self, form):
        """
        Handle valid form submission and delete the associated object.

        :param form: Bound form instance with valid input data
        :return: HTTP response generated from the context data after object deletion
        :rtype: HttpResponse
        :raises: None
        """
        self._delete_files()
        return self.render_to_response(self.get_context_data(form=form))


class UploadSubmissionFile(HtmxMixin, AuthorFilteringView, TableRenderingContext, FormView):
    """
    A view to allow an author to upload files during the submission or a revision.

    Uploaded files can be manuscript, data-figure files and cover letter file.

    This view is intended to be used from inside a small modal.
    """

    # HELP: IIC, we are mimicing a DetailView, but I don't see the gain (and this confuses me...)
    model = Article
    pk_url_kwarg = "article_id"
    render_table = False
    """
    Flag to signal whether ot render the upload form or the full files table.
    See also step4.views.ModalRenderingMixin
    """

    def setup(self, request, *args, **kwargs):
        """
        Set up the view by initializing the object and file type attributes.

        :param request: The HTTP request object.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :raises self.model.DoesNotExist: If the object with the given `article_id` is not found.
        :return: None
        """
        super().setup(request, *args, **kwargs)
        self.object = self.model.objects.get(pk=self.kwargs["article_id"])
        self.file_type = self.kwargs["file_type"]

    def get_template_names(self):
        """
        Determine the template names based on the `render_table` attribute.

        :raises AttributeError: If `render_table` is not defined or is not accessible.
        :return: List of template names to be used.
        :rtype: list of str
        """
        if self.render_table:
            return ["wjs_submission/step6/includes/files_table.html"]
        return ["wjs_submission/step6/includes/upload_file.html"]

    def get_initial(self):
        """
        Get the initial data for the form, populating specific fields based on the file type.

        :raises AttributeError: If any required attribute for file type processing is missing or improperly configured.
        :raises TypeError: If an incorrect type is encountered during label processing.
        :return: A dictionary containing the initial data for the form.
        :rtype: dict
        """
        initial = super().get_initial()
        if self.file_type == "manuscript":
            initial["label"] = self.request.journal.submissionconfiguration.submission_file_text
        elif self.file_type == "data":
            initial["label"] = get_setting(
                "styling", "submission_figures_data_title", self.request.journal
            ).process_value()
        return initial

    def get_form_class(self):
        """
        Return the form class to use based on whether this is a revision.

        :return: Form class to use.
        :rtype: django.forms.Form
        """
        if is_revision(self.object):
            return RevisionUploadArticleForm

        return UploadArticleForm

    def get_form_kwargs(self):
        """
        Retrieve additional keyword arguments for initializing a form.

        This method updates the keyword arguments with attributes such as
        `file_type`, `instance`, and `user` required to initialize a form
        instance for a request.

        :return: A dictionary containing the additional keyword arguments for
            the form initialization.
        :rtype: dict
        :raises AttributeError: If any required attribute for updating the
            form keyword arguments is not present.
        """
        kwargs = super().get_form_kwargs()
        kwargs["file_type"] = self.file_type
        kwargs["instance"] = self.object
        kwargs["user"] = self.request.user
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        """If the form is valid, save the file and return a response."""
        form.save()
        self.render_table = True
        response = self.render_to_response(self.get_context_data(form=form))
        response.headers["HX-Retarget"] = f"#files_table_{self.file_type}"
        response.headers["HX-Trigger-After-Swap"] = "closeModal"
        return response

    def form_invalid(self, form):
        """Save form and redirect via HTMX."""
        response = super().form_invalid(form)
        response["HX-Retarget"] = "#htmxModalContent"
        return response
