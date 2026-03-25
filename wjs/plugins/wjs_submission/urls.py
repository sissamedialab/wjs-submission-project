from django.urls import path

from .plugin_settings import MANAGER_URL
from .revision import (
    RevisionStartConfirmView,
    RevisionStartFullView,
    RevisionStartMetadataView,
)
from .step1 import SubmissionStep1RedirectView, SubmissionStep1View
from .step2 import SubmissionStep2View
from .step3 import SubmissionStep3View
from .step4 import AddAuthorView, SubmissionStep4View
from .step4.views import AddCollaborationView, ReorderAuthorsView, SaveCorrespondingAuthorView
from .step5 import SubmissionStep5View
from .step6 import (
    DeleteSubmissionFile,
    RenderSubmissionFile,
    SubmissionStep6View,
    UploadSubmissionFile,
)
from .step7 import AddFundingView, SubmissionStep7View
from .step7.views import DeleteFundingView
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
    path(
        "submission/closed/",
        ClosedSubmissionsView.as_view(),
        name="wjs_submission_closed",
    ),
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
        "submission/<int:article_id>/6/upload/<str:file_type>/",
        UploadSubmissionFile.as_view(),
        name="wjs_submission_6_upload",
    ),
    path(
        "submission/<int:article_id>/6/delete/<str:file_type>/<int:file_id>/",
        DeleteSubmissionFile.as_view(),
        name="wjs_submission_6_delete",
    ),
    path(
        "submission/<int:article_id>/6/render/<str:file_type>/",
        RenderSubmissionFile.as_view(),
        name="wjs_submission_6_render",
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
    path(
        "keyword-autocomplete/",
        FreeKeywordAutocomplete.as_view(),
        name="keyword-autocomplete",
    ),
    path("submission/<int:article_id>/reorder-author/", ReorderAuthorsView.as_view(), name="wjs-reorder-author"),
    path(
        "submission/<int:article_id>/corresponding-author/",
        SaveCorrespondingAuthorView.as_view(),
        name="wjs-save-author",
    ),
    path("add-author/", AddAuthorView.as_view(), name="add-author"),
    path("add-collaboration/", AddCollaborationView.as_view(), name="add-collaboration"),
    path("add-funding/", AddFundingView.as_view(), name="add-funding"),
    path("delete-funding/", DeleteFundingView.as_view(), name="delete-funding"),
    path("add-funding/revision/", AddFundingView.as_view(is_revision=True), name="add-funding-revision"),
    path("delete-funding/revision/", DeleteFundingView.as_view(is_revision=True), name="delete-funding-revision"),
    path(
        "submission/<int:article_id>/confirm/",
        RevisionStartConfirmView.as_view(),
        name="wjs_submission_revision_confirm",
    ),
    path(
        "submission/<int:article_id>/metadata/",
        RevisionStartMetadataView.as_view(),
        name="wjs_submission_revision_metadata",
    ),
    path(
        "submission/<int:article_id>/revision/",
        RevisionStartFullView.as_view(),
        name="wjs_submission_revision_full",
    ),
]
