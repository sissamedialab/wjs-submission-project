from importlib import import_module

from core.middleware import GlobalRequestMiddleware
from core.models import Account
from django.contrib.messages.storage import default_storage
from django.http import HttpRequest, QueryDict
from journal.models import Journal


def create_rich_fake_request(
    journal: Journal,
    settings: dict,
    user: Account = None,
) -> HttpRequest:
    """Create a fake_factory request suitable for rendering templates and storing django messages."""
    # - cron/management/commands/send_publication_notifications.py
    # - workflow-element-complete triggers core.workflow.workflow_next() that can store messages
    fake_request = HttpRequest()

    fake_request.user = user

    fake_request.FILES = None
    fake_request.META = {}

    fake_request.META = {"REMOTE_ADDR": "127.0.0.1"}
    fake_request.model_content_type = None

    if journal:
        fake_request.journal = journal
        fake_request.site_type = journal
        fake_request.press = journal.press
        fake_request.repository = None

    fake_request.GET = QueryDict("", mutable=True)
    fake_request.POST = QueryDict("", mutable=True)
    GlobalRequestMiddleware.process_request(fake_request)
    # messages are required by review functions
    original_message_storage = settings.MESSAGE_STORAGE
    settings.MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
    fake_request._messages = default_storage(fake_request)  # noqa: SLF001
    settings.MESSAGE_STORAGE = original_message_storage
    fake_request.COOKIES = {}
    engine = import_module(settings.SESSION_ENGINE)
    fake_request.session = engine.SessionStore()
    return fake_request
