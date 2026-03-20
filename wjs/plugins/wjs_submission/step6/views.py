import logging
from pathlib import Path

from core import models as core_models
from django.db.models import QuerySet
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.views.generic import DeleteView, DetailView, FormView, UpdateView
from submission.models import Article
from utils.setting_handler import get_setting

from .. import settings as submission_settings
from ..conversion import get_feedback_logfile, get_feedback_ws_url, report_yakunin_errors
from ..mixins import AuthorFilteringView, HtmxMixin, StepCheckView
from ..models import RevisionStorage
from ..workflow import (
    is_revision,
    is_revision_confirm,
    is_revision_full,
    is_revision_metadata,
)
from .forms import RevisionStep6Form, RevisionUploadArticleForm, SubmissionStep6Form, UploadArticleForm

logger = logging.getLogger(__name__)
TASK_LOG_PREFIX = "conversion-task-log"


def get_files(article: Article) -> dict:
    """
    Return a dictionary of files querysets.

    This is intended to be used to update the context data of step6 and step8 views
    and those of Upload/Delete files views.

    Files are taken from revisionstorage only for full revision, in the other cases we will get them from article.
    """
    files_by_type = {}
    if is_revision_full(article):
        data = RevisionStorage.objects.get(article=article).data

        if file_id := data["manuscript_files"]:
            files_by_type["manuscript_files"] = core_models.File.objects.filter(id=file_id)
        elif file_id := data["source_files"]:
            # Show source file if manuscript conversion failed
            files_by_type["manuscript_files"] = core_models.File.objects.filter(id=file_id)
        else:
            files_by_type["manuscript_files"] = core_models.File.objects.none()

        # supplementary files aka electronic supplementary material
        files_by_type["esm"] = core_models.File.objects.filter(
            id__in=data["supplementary_files"],
        )

        # data/figure files aka administrative files
        files_by_type["data"] = core_models.File.objects.filter(
            id__in=data["data_figure_files"],
        )

    else:
        files_by_type["manuscript_files"] = (
            article.manuscript_files if article.manuscript_files.exists() else article.source_files
        )
        files_by_type["data"] = article.data_figure_files

        # ESM are core.SupplementaryFiles objects (i.e. not simple core.File objects)
        # we need to "convert" them (otherwise calls such as file.original_filename won't work)
        files_by_type["esm"] = core_models.File.objects.filter(
            pk__in=article.supplementary_files.all().values_list("file_id", flat=True),
        )

    return files_by_type


def get_conversion_status(article: Article, view) -> dict:
    """
    Return a dictionary with info about the PDF conversion of the given article.

    This is intended to be used to update the context data of views that show the manuscript
    (step6 article_form and files_table and step 8).

    ⚠ here there be 🐉s
    We follow the conventions described in workflow.create_log_file().
    We assume that the log file can contain lines starting with WARNING, ERROR, or FAIL;
    these also we include in the context.

    """
    context = {
        "feedback_ws_url": "",
        "conversion_log_file": None,
        "conversion_log_url": None,
        "conversion_log": None,
        "conversion_status": None,
        "conversion_result": None,
    }
    context["show_detailed_log"] = submission_settings.YAKUNIN_SHOW_DETAILED_LOG

    if article.submission_data.feedback_uuid:
        feedback_ws_url = get_feedback_ws_url(
            view.request,
            article.pk,
            view.request.user.pk,
            article.submission_data.feedback_uuid,
        )
        log_filename = get_feedback_logfile(article.submission_data.feedback_uuid)
        log_file = core_models.File.objects.filter(
            article_id=article.pk,
            original_filename=log_filename,
        ).first()
        context["feedback_ws_url"] = feedback_ws_url

        if log_file:
            context["conversion_log_file"] = log_file
            # Filter log to only include lines starting with WARNING, ERROR, or FAIL
            # (these are intended to be shown direcly on the page)
            full_log = Path(log_file.self_article_path()).read_text(encoding="utf-8")
            filtered_lines = report_yakunin_errors(full_log, include_warnings=True)
            context["conversion_log_url"] = reverse(
                "download_single_file",
                kwargs={
                    "article_id": log_file.article_id,
                    "file_id": log_file.pk,
                },
            )
            context["conversion_log"] = "\n".join(filtered_lines)
            context["conversion_status"] = log_file.label
            # It is possible that the WS consumer did not update the log file status;
            # in this case we can assume that if a manuscript file exists, then the process is completed.
            if log_file.label == "unknown" and article.manuscript_files.exists():
                context["conversion_status"] = "completed"
                logger.warning(f"Forced completed state on logfile for {article.submission_data.feedback_uuid}")
            context["conversion_result"] = log_file.description
        else:
            context["conversion_log_file"] = None
            context["conversion_log_url"] = None
            context["conversion_log"] = ""
            context["conversion_status"] = "unknown"
            context["conversion_result"] = "unknown"

        context["conversion_result_color"] = {
            "failed": "danger",
            "error": "danger",
            "warning": "warning",
            "success": "success",
        }.get(context["conversion_result"], "warning")
    return context


class SubmissionStep6View(AuthorFilteringView, StepCheckView, UpdateView):
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

        :param kwargs: Additional keyword arguments passed to the method.
        :return: The modified context dictionary with additional article files and related attributes.
        """
        context = super().get_context_data(**kwargs)

        # Include files (manuscript_files, data_figure_files, etc.)
        context.update(get_files(article=self.object))

        # Include info about the conversion status
        context.update(get_conversion_status(article=self.object, view=self))

        return context


class TableRenderingContext:
    @cached_property
    def _article(self) -> Article:
        """Retrieve article object."""
        return Article.objects.get(pk=self.kwargs["article_id"])

    def get_context_data(self, **kwargs):
        """
        Add to context the data required to render the files table.

        :param kwargs: Additional keyword arguments passed to the method.
        :return: The modified context dictionary with additional article files and related attributes.
        :rtype: dict
        """
        context = super().get_context_data(**kwargs)
        context["article"] = self._article

        file_type = self.kwargs.get("file_type")
        context["button_name"] = f"trigger_{file_type}"
        context["file_type"] = file_type

        files_by_type = get_files(self._article)
        if file_type == "manuscript":
            context["files_list"] = files_by_type["manuscript_files"]
            context["show_conversion"] = True
            context.update(get_conversion_status(self._article, view=self))

        elif file_type == "data":
            context["files_list"] = files_by_type["data"]
        elif file_type == "esm":
            context["files_list"] = files_by_type["esm"]

        return context


class RenderSubmissionFile(HtmxMixin, AuthorFilteringView, TableRenderingContext, DetailView):
    model = Article
    pk_url_kwarg = "article_id"
    template_name = "wjs_submission/step6/includes/files_table.html"
    context_object_name = "article"

    def get_context_data(self, **kwargs) -> dict:
        """
        Add read-only flag if we are in step-8.

        That following flag is used by files_tables.html
        to show/hide the delete button and to run the required-fields checklist update.

        In step-8 it should be set to True, elsehwere to False (or just be absent).
        """
        context = super().get_context_data(**kwargs)
        if self.object.current_step > 7 and not is_revision(self.object):
            context["read_only"] = True
        context["skip_connect_websocket"] = True
        return context


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

    def _delete_conversion_log(self):
        """Delete the conversion log file."""
        # TODO: stop any running conversion!
        try:
            [
                f.delete()
                for f in core_models.File.objects.filter(
                    article_id=self.kwargs["article_id"],
                    original_filename__startswith=TASK_LOG_PREFIX,
                )
            ]
        except Exception:
            # Any failure here is not critical, but we should log it.
            logger.exception("Error deleting conversion log file")
        # Memento: if self._article was a @property (i.e. not a @cached_property as it's now)
        # it cannot be used to set/store/save values onto submission_data as done below:
        self._article.submission_data.feedback_uuid = None
        self._article.submission_data.save()

    def _delete_files(self):
        """
        Delete the selected file.

        - If file to delete is a source file, manuscript files are cleared.
        - If file to delete is a manuscript file, source files are cleared.
        - The file object itself is deleted.

        For revisions:
        - Only delete file objects that are NOT in the article's existing file slots.
        - Files from the original article are preserved; only their references in RevisionStorage are removed.
        - Newly uploaded files (not in original article) are deleted completely.
        """
        if not is_revision(self._article):
            if self.object in self._article.source_files.all():
                for f in self._article.manuscript_files.all():
                    f.delete()
                self._delete_conversion_log()
            if self.object in self._article.manuscript_files.all():
                for f in self._article.source_files.all():
                    f.delete()
                self._delete_conversion_log()
            # Note that SupplementaryFile objects are cascade-deleted when the relative File is deleted.
            self.object.delete()
            self._article.refresh_from_db()
        else:
            revision_storage = RevisionStorage.objects.get(article=self._article)
            file_type = self.kwargs["file_type"]

            if file_type == "manuscript":
                # I'ts possible that the author deletes the "manuscript", before the conversion is fihished.
                # Ensure that the object id is either the manuscript or source slot,
                # then delete all existing Files refrenced by revision storage manuscript or source slots.
                #
                # below, "filter(bool...)" is needed because "empty" slots hold the "Null" value,
                # which makes for a valid item in a list, but not for a valid id in a query
                # (the "set" is not strictly necessary :)
                fileids_to_delete = set(
                    filter(bool, [revision_storage.data["manuscript_files"], revision_storage.data["source_files"]])
                )
                if self.object.id in fileids_to_delete:
                    revision_storage.data["manuscript_files"] = None
                    revision_storage.data["source_files"] = None
                    for f in core_models.File.objects.filter(id__in=fileids_to_delete):
                        f.delete()
                else:
                    logger.error(
                        f"Unexpected file to delete {self.object.id} not manuscript nor source"
                        f" for article {self._article.id}",
                    )
                # Always delete the conversion logs: when the source or the manuscript change,
                # they have no reason to be kept.
                self._delete_conversion_log()

            elif file_type == "data":
                revision_storage.data["data_figure_files"].remove(self.object.id)
                if self.object.id not in set(self._article.data_figure_files.values_list("id", flat=True)):
                    self.object.delete()

            elif file_type == "esm":
                # Note that supplementary files are core.SupplementaryFiles, not core.File.
                # Also, RevisionStorage holds a reference to a File object.
                revision_storage.data["supplementary_files"].remove(self.object.id)
                if esm := self.object.supplementaryfile_set.first():  # noqa: SIM102
                    if esm.id not in set(self._article.supplementary_files.values_list("id", flat=True)):
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

    Uploaded files can be manuscript, administrative files (aka data-figure files) and supplementary files.

    This view is intended to be used from inside a small modal.
    """

    # We are "mimicing" a DetailView because we need to get the article object anyway,
    # instead of doing Article.objects.get in multiple places (get_form_kwargs, get_form_class,...)
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
