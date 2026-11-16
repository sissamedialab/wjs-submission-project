"""PopulateStep6 copies cas/das (and their free text) into the revision storage."""

import pytest
from plugins.wjs_submission.models import ArticleSubmission, RevisionStorage
from plugins.wjs_submission.revision.logic import PopulateStep6
from submission.models import Article


@pytest.mark.django_db
def test_populate_step6_copies_cas_das_text(article: Article):
    """The single cas_text/das_text field is copied alongside cas/das."""
    article.submission_data.cas = ArticleSubmission.CasDeclaration.OTHER
    article.submission_data.cas_text = "some code statement"
    article.submission_data.das = ArticleSubmission.DasDeclaration.OTHER
    article.submission_data.das_text = "some data statement"
    article.submission_data.save()
    revision_storage = RevisionStorage.objects.create(article=article)

    PopulateStep6(revision_storage)(commit=True)

    assert revision_storage.data["cas_text"] == "some code statement"
    assert revision_storage.data["das_text"] == "some data statement"
