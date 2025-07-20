from django.urls import path

from .plugin_settings import MANAGER_URL
from .step1 import SubmissionStep1View
from .step2 import SubmissionStep2
from .views import ArxivMicroservice, Manager, RedirectToComplete

urlpatterns = [
    path("manager/", Manager.as_view(), name=MANAGER_URL),
    path("arxiv/", ArxivMicroservice.as_view(), name="arxiv_microservice"),
    path("submission/1/", SubmissionStep1View.as_view(), name="wjs_submission_1"),
    path(
        "submission/<int:article_id>/1/",
        SubmissionStep1View.as_view(),
        name="wjs_submission_1",
    ),
    path(
        "submission/<int:article_id>/2/",
        SubmissionStep2.as_view(),
        name="wjs_submission_2",
    ),
    path(
        "submission/<int:article_id>/3/",
        SubmissionStep2.as_view(),
        name="wjs_submission_3",
    ),
    path(
        "submission/<int:article_id>/4/",
        SubmissionStep2.as_view(),
        name="wjs_submission_4",
    ),
    path(
        "submission/<int:article_id>/5/",
        SubmissionStep2.as_view(),
        name="wjs_submission_5",
    ),
    path(
        "submission/<int:article_id>/6/",
        SubmissionStep2.as_view(),
        name="wjs_submission_6",
    ),
    path(
        "submission/<int:article_id>/7/",
        SubmissionStep2.as_view(),
        name="wjs_submission_7",
    ),
    path(
        "submission/<int:article_id>/8/",
        SubmissionStep2.as_view(),
        name="wjs_submission_8",
    ),
    path(
        "submission/<int:article_id>/0/",
        RedirectToComplete.as_view(),
        name="wjs_submission_0",
    ),
]
