import uuid
from io import BytesIO

from core import files as core_files
from core import models as core_models
from core.models import Account
from django.core.files import File
from django.http import HttpRequest
from django_q.tasks import async_task
from events import logic as event_logic
from submission.models import Article

from . import settings as submission_settings

TASK_LOG_PREFIX = "conversion-task-log"


def start_source_conversion(
    article: Article, request: HttpRequest, new_file: core_models.File, is_revision: bool = False
):
    """
    Initiate source file conversion process and raise necessary events.

    This function generates a unique feedback UUID for the article submission data, saves it, builds feedback
    workspace name and URL, creates a log file, and raises the ON_ARTICLE_FILE_UPLOAD event with all relevant
    data. If simulation mode for Yakunin is enabled, it triggers an asynchronous task for simulation.

    :param article: The article object associated with the source file conversion
    :type article: Article
    :param request: The HTTP request object initiating the conversion
    :type request: HttpRequest
    :param new_file: The newly uploaded file object for the article
    :type new_file: File
    :param is_revision: Flag indicating if the upload is a revision, default is False
    :type is_revision: bool
    :raises AttributeError: If article submission data attributes are missing or improperly set
    :raises ValueError: If any key component of the event logic or settings is invalid
    :return: None
    :rtype: NoneType
    """
    article_id = article.pk
    user_id = request.user.pk
    article.submission_data.feedback_uuid = uuid.uuid4()
    article.submission_data.save()
    feedback_uuid = article.submission_data.feedback_uuid
    feedback_ws_name = get_feedback_ws_name(article_id, user_id, feedback_uuid)
    feedback_ws_url = get_feedback_ws_url(request, article_id, user_id, feedback_uuid)
    create_log_file(article=article, feedback_uuid=feedback_uuid, owner=request.user)
    event_logic.Events.raise_event(
        event_logic.Events.ON_ARTICLE_FILE_UPLOAD,
        request=request,
        file_id=new_file,
        original_filename=new_file.original_filename,
        file_type="manuscript:async",
        article=article,
        feedback_ws_url=feedback_ws_url,
        feedback_ws_name=feedback_ws_name,
        feedback_uuid=feedback_uuid,
        is_revision=is_revision,
    )
    if submission_settings.SIMULATE_YAKUNIN:
        async_task(simulate_yakunin_call, feedback_ws_name, task_name="simulate-feedback")


def report_yakunin_errors(full_log: str, include_warnings=False) -> list[str]:
    """
    Extract lines from a log that begin with specific error indicators.

    This function processes a multiline log string and identifies lines
    that start with predefined prefixes ("ERROR", "FAIL").
    It returns a list of such lines for further analysis.
    If include_warnings is True, it also includes lines starting with "WARNING".

    :param full_log: The complete log to be analyzed
    :type full_log: str
    :param include_warnings: If True, include warnings in the log.
    :type include_warnings: bool
    :return: A list of lines starting with "ERROR", or "FAIL"
    :rtype: list[str]
    """
    levels = ("ERROR", "FAIL")
    if include_warnings:
        levels += ("WARNING",)
    return [line for line in full_log.splitlines() if line.startswith(levels)]


def report_yakunin_warnings(full_log: str) -> list[str]:
    """
    Extract lines from a log that begin with specific warning indicators.

    This function processes a multiline log string and identifies lines
    that start with predefined prefixes ("WARNING").
    It returns a list of such lines for further analysis.

    :param full_log: The complete log to be analyzed
    :type full_log: str
    :return: A list of lines starting with "WARNING"
    :rtype: list[str]
    """
    return [line for line in full_log.splitlines() if line.startswith("WARNING")]


def get_feedback_ws_name(workflow_pk: int, user_pk: int, feedback_uuid: uuid.UUID) -> str | None:
    """Compute a paper/user/situation unique name for the feedback channel."""
    return f"submission-{workflow_pk}-{user_pk}-{feedback_uuid}"


def get_feedback_ws_url(request: HttpRequest, workflow_pk: int, user_pk: int, feedback_uuid: uuid.UUID) -> str | None:
    """Compute the full URL of the websocket feedback consumer."""
    feedback_ws_name = get_feedback_ws_name(workflow_pk, user_pk, feedback_uuid)
    return f"{'wss' if request.is_secure() else 'ws'}://{request.get_host()}/ws/feedback/{feedback_ws_name}/{workflow_pk}/{feedback_uuid}/"


def get_feedback_logfile(feedback_uuid: uuid.UUID) -> str:
    """Get the name of the log file for a given feedback UUID."""
    return f"{TASK_LOG_PREFIX}_{feedback_uuid}.log"


def create_log_file(article: Article, feedback_uuid: uuid.UUID, owner: Account) -> core_models.File:
    """
    Create an empty log file to persist status and result of the manuscript conversion process.

    Important conventions to note:
    - original filename: <PREFIX>_<UUID>.log
      the UUID will be used in the websocket name;
      this should allow a WS consumer that needs to update the log to get the correct log file
      even if the author starts multiple conversions before one is finished.
      Also, this allows WS clients to get the correct websocket for feedback.

    - label: here the status should be stored ("notstarted", "running", "completed")

    - description: here the most recent result should be stored ("success", "warning", etc.);
      note that the most important result should always be available.
      E.g. the WS consumer makes sure that if we receive a 5 messages, the following happens:
      messages result sequence: info - warn - info - error - info
      description value:        info - warn - warn - error - error
      I.e., "warnings" win over "info" and "errors" win over "warnings"

    :return: A tuple containing the created File object and the generated UUID string.
    :rtype: tuple[core_models.File, str]
    """
    return core_files.save_file_to_article(
        File(
            BytesIO(b""),
            name=get_feedback_logfile(feedback_uuid),
        ),
        article=article,
        owner=owner,
        label="not started",
        description="unknown",
    )


def simulate_yakunin_call(ws_name):
    """
    Emulate a Yakunin session.

    :param ws_name: name of the websocket to run
    """
    from .management.commands.send_feedback import Command as FakeYakunin  # noqa: PLC0415

    # FIXME: FakeYakunin must be updated to reflect actual yakunin code
    FakeYakunin().handle(ws_name=ws_name)
