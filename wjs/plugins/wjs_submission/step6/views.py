from core import models as core_models
from core.models import File
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse_lazy
from django.views.generic import DeleteView, DetailView, FormView, UpdateView
from django_q.tasks import async_task
from events import logic as event_logic
from submission.models import Article
from utils.setting_handler import get_setting

from .. import settings as submission_settings
from ..management.commands.send_feedback import Command as FakeYakunin
from ..mixins import AuthorFilteringView, HtmxMixin, StepCheckView
from .forms import SubmissionStep6Form, UploadArticleForm


class SubmissionStep6View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 6
    form_class = SubmissionStep6Form
    template_name = "wjs_submission/step6/article_form.html"

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


class TableRenderingContext:
    @property
    def _article(self) -> Article:
        """Retrieve article object."""
        return Article.objects.get(pk=self.kwargs["article_id"])

    def get_context_data(self, **kwargs):
        """
        Add to context the data required to render the files table.

        :param kwargs: Additional keyword arguments passed to the method.
        :return: The modified context dictionary with additional article files and related attributes.
        :rtype: dict
        :raises Article.DoesNotExist: If the article with the provided `article_id` does not exist.
        """
        context = super().get_context_data(**kwargs)
        context["article"] = self._article
        if self.kwargs["file_type"] == "manuscript":
            context["show_conversion"] = True
            context["files_list"] = (
                context["article"].manuscript_files
                if context["article"].manuscript_files.exists()
                else context["article"].source_files
            )
            context["failed_conversion_log"] = core_models.File.objects.filter(
                article_id=context["article"].pk, label="Failed conversion log ConvertManuscriptToPdf"
            ).first()
        elif self.kwargs["file_type"] == "data":
            context["files_list"] = context["article"].data_figure_files
        elif self.kwargs["file_type"] == "administrative":
            context["files_list"] = context["article"].submission_data.administrative_files
        context["button_name"] = f"trigger_{self.kwargs['file_type']}"
        context["file_type"] = self.kwargs["file_type"]
        return context


class RenderSubmissionFile(HtmxMixin, AuthorFilteringView, TableRenderingContext, DetailView):
    model = Article
    pk_url_kwarg = "article_id"
    template_name = "wjs_submission/step6/includes/files_table.html"
    context_object_name = "article"


class DeleteSubmissionFile(HtmxMixin, AuthorFilteringView, TableRenderingContext, DeleteView):
    model = File
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
        if self.object in self._article.source_files.all():
            for f in self._article.manuscript_files.all():
                f.delete()
        if self.object in self._article.manuscript_files.all():
            for f in self._article.source_files.all():
                f.delete()
        self.object.delete()
        self._article.refresh_from_db()

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
    A view to allow an author to upload files during the submission of a revision.

    Uploaded files can be manuscript, data-figure files and cover letter file.

    This view is intended to be used from inside a small modal.
    """

    model = Article
    pk_url_kwarg = "article_id"
    form_class = UploadArticleForm
    render_table = False
    """
    Flag to signal whether ot render the upload form or the full files table
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
        return kwargs

    def form_valid(self, form):
        """If the form is valid, save the file and return a response."""
        form.save()
        new_file = form.new_file
        if new_file and self.file_type == "manuscript":
            article_id = self.object.pk
            user_id = self.request.user.pk
            feedback_ws_name = get_feedback_ws_name(article_id, user_id)
            feedback_ws_url = get_feedback_ws_url(self.request, article_id, user_id)
            event_logic.Events.raise_event(
                event_logic.Events.ON_ARTICLE_FILE_UPLOAD,
                request=self.request,
                file_id=new_file,
                original_filename=new_file.original_filename,
                file_type="manuscript:async",
                article=self.object,
                feedback_ws_url=feedback_ws_url,
                feedback_ws_name=feedback_ws_name,
            )
            if submission_settings.SIMULATE_YAKUNIN:
                async_task(simulate_yakunin_call, feedback_ws_name, task_name="simulate-feedback")
        self.render_table = True
        response = self.render_to_response(self.get_context_data(form=form))
        response.headers["HX-Retarget"] = f"#files_table_{self.file_type}"
        response.headers["HX-Trigger-After-Swap"] = "closeModal"
        return response


def get_feedback_ws_name(workflow_pk: int, user_pk: int) -> str:
    """Compute a paper/user/situation unique name for the feedback channel."""
    return f"submission-{workflow_pk}-{user_pk}"


def get_feedback_ws_url(request: HttpRequest, workflow_pk: int, user_pk: int) -> str:
    """Compute the full URL of the websocket feedback consumer."""
    feedback_ws_name = get_feedback_ws_name(workflow_pk, user_pk)
    return f"{'wss' if request.is_secure() else 'ws'}://{request.get_host()}/ws/feedback/{feedback_ws_name}/"


def simulate_yakunin_call(ws_name):
    FakeYakunin().handle(ws_name=ws_name)
