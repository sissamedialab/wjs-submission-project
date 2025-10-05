from django.urls import path

from .plugin_settings import MANAGER_URL
from .step1 import SubmissionStep1RedirectView, SubmissionStep1View
from .step2 import SubmissionStep2View
from .step3 import SubmissionStep3View
from .step4 import AddAuthorView, SubmissionStep4View
from .step4.views import AddCollaborationView
from .step5 import SubmissionStep5View
from .step6 import SubmissionStep6View
from .step7 import SubmissionStep7View
from .step8 import SubmissionStep8View
from .views import (
    ArxivMicroservice,
    ClosedSubmissionsView,
    FreeKeywordAutocomplete,
    Manager,
    RedirectToComplete,
    SubmissionLastStepRedirectView,
)

urlpatterns = [
    path("manager/", Manager.as_view(), name=MANAGER_URL),
    path("arxiv/", ArxivMicroservice.as_view(), name="arxiv_microservice"),
    path("submission/", SubmissionStep1View.as_view(), name="wjs_submission_1"),
    path("submission/closed/", ClosedSubmissionsView.as_view(), name="wjs_submission_closed"),
    path(
        "submission/<int:article_id>/continue/",
        SubmissionLastStepRedirectView.as_view(),
        name="wjs_submission_continue",
    ),
    path(
        "submission/<int:article_id>/",
        SubmissionStep1RedirectView.as_view(),
        name="wjs_submission_1_fallback",
    ),
    path(
        "submission/<int:article_id>/1/",
        SubmissionStep1View.as_view(),
        name="wjs_submission_1",
    ),
    path(
        "submission/<int:article_id>/2/",
        SubmissionStep2View.as_view(),
        name="wjs_submission_2",
    ),
    path(
        "submission/<int:article_id>/3/",
        SubmissionStep3View.as_view(),
        name="wjs_submission_3",
    ),
    path(
        "submission/<int:article_id>/4/",
        SubmissionStep4View.as_view(),
        name="wjs_submission_4",
    ),
    path(
        "submission/<int:article_id>/5/",
        SubmissionStep5View.as_view(),
        name="wjs_submission_5",
    ),
    path(
        "submission/<int:article_id>/6/",
        SubmissionStep6View.as_view(),
        name="wjs_submission_6",
    ),
    path(
        "submission/<int:article_id>/7/",
        SubmissionStep7View.as_view(),
        name="wjs_submission_7",
    ),
    path(
        "submission/<int:article_id>/8/",
        SubmissionStep8View.as_view(),
        name="wjs_submission_8",
    ),
    path(
        "submission/<int:article_id>/0/",
        RedirectToComplete.as_view(),
        name="wjs_submission_0",
    ),
    path("keyword-autocomplete/", FreeKeywordAutocomplete.as_view(), name="keyword-autocomplete"),
    path("add-author/", AddAuthorView.as_view(), name="add-author"),
    path("add-collaboration/", AddCollaborationView.as_view(), name="add-collaboration"),
]
