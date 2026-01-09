from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import RedirectView

from ..mixins import AuthorFilteringView
from ..models import RevisionStorage
from .logic import (
    BaseSetupRevisionStorage,
    SetupRevisionStorageConfirm,
    SetupRevisionStorageFull,
    SetupRevisionStorageMetadata,
)


class BaseRevisionStartView(AuthorFilteringView, RedirectView):
    """Helper view to start a revision submission process."""

    revision_storage: RevisionStorage
    flow_init_class: type[BaseSetupRevisionStorage]

    def get(self, request, *args, **kwargs):
        """
        Initialize the RevisionStorage object.

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        try:
            self._init_revision_flow(kwargs["article_id"])
            return super().get(request, *args, **kwargs)
        except ValueError as e:
            return render(request, "wjs_submission/revision/error.html", context={"error": str(e)})

    def _init_revision_flow(self, article_id: int):
        flow_init = self.flow_init_class(article_id)
        flow_init.run()

    def get_redirect_url(self, *args, **kwargs):  # noqa: PLR6301
        """
        Redirect to the next step.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_1", kwargs={"article_id": kwargs["article_id"]})


class RevisionStartConfirmView(BaseRevisionStartView):
    flow_init_class = SetupRevisionStorageConfirm


class RevisionStartMetadataView(BaseRevisionStartView):
    flow_init_class = SetupRevisionStorageMetadata


class RevisionStartFullView(BaseRevisionStartView):
    flow_init_class = SetupRevisionStorageFull
