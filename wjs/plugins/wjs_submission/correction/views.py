"""Views for the correction (erratum/addendum) submission workflow."""

from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import RedirectView

from ..mixins import AuthorFilteringView
from .logic import CORRECTION_RELATIONSHIPS, SetupCorrectionStorage


class CorrectionStartView(AuthorFilteringView, RedirectView):
    """
    Entry point: start a correction (erratum/addendum) submission.

    Reads ``article_id`` (the published article) and ``relationship``
    (``"erratum"`` or ``"addendum"``) from URL kwargs, then delegates to
    :class:`SetupCorrectionStorage` to create/resume the correction article,
    and redirects to step 1 of the submission workflow.
    """

    def get(self, request, *args, **kwargs):
        """Handle GET request to start a correction submission flow."""
        article_id = kwargs["article_id"]
        relationship = kwargs["relationship"]
        if relationship not in CORRECTION_RELATIONSHIPS:
            return render(
                request,
                "wjs_submission/correction/error.html",
                context={
                    "error": f"Invalid relationship: {relationship}",
                    "article_id": article_id,
                },
            )
        try:
            setup = SetupCorrectionStorage(
                article_id=article_id,
                relationship=relationship,
                request=request,
            )
            to_article = setup.run()
            kwargs["article_id"] = to_article.id
            return super().get(request, *args, **kwargs)
        except ValueError as e:
            return render(
                request,
                "wjs_submission/correction/error.html",
                context={
                    "error": str(e),
                    "article_id": article_id,
                },
            )

    @staticmethod
    def get_redirect_url(*args, **kwargs) -> str:  # noqa: ARG004
        """Redirect to step 1 of the submission workflow with the correction article."""
        return reverse_lazy(
            "wjs_submission_1",
            kwargs={"article_id": kwargs["article_id"]},
        )
