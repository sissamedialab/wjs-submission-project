from collections.abc import Callable

import pytest
from core.middleware import GlobalRequestMiddleware
from core.models import Account
from identifiers.models import Identifier
from journal.models import Journal
from plugins.wjs_submission.arxiv import (
    ArXivIDAlreadyUsedError,
    ArXivIDContinueSubmissionError,
    ArXivToArticle,
    HandleArticleCreation,
)
from plugins.wjs_submission.step1.forms import SubmissionStep1Form
from submission.models import STAGE_UNASSIGNED, STAGE_UNSUBMITTED, Article


@pytest.mark.parametrize("unsaved_article", [True, False])
@pytest.mark.django_db
def test_create_article_without_arxiv_id(
    journal: Journal, install_plugins: Callable, user: Account, unsaved_article: bool
):
    """
    Article is always created by HandleArticleCreation and base data are set when no arxiv_id is provided.

    Verifies successful creation of the article, validates its attributes, and ensures it is
    in the correct initial state.

    :param journal: An instance of the Journal to which the article belongs
    :param install_plugins: A callable to install necessary plugins for the operation
    :param user: An Account instance representing the article's owner
    :param unsaved_article: A boolean indicating whether the article should be created in
        an unsaved state
    :raises AssertionError: If article creation or validation of attributes fails
    """
    form_data = {
        "copyright_notice": "on",
        "competing_interests": "on",
        "submission_requirements": "c",
        "comments_editor": "d",
    }
    article = None
    if unsaved_article:
        article = Article()
    service = HandleArticleCreation(user, form_data, journal, article=article)
    article = service.run()
    assert article.pk
    assert article.journal == journal
    assert article.owner == user
    assert article.correspondence_author == user
    assert not article.title
    assert not article.abstract
    assert article.stage == STAGE_UNSUBMITTED
    assert article.current_step == 0


@pytest.mark.django_db
def test_create_article_with_arxiv_id(
    journal: Journal, install_plugins: Callable, user: Account, arxiv_metadata: Callable
):
    """
    Article is always created by HandleArticleCreation and base data are set when arxiv_id is provided.

    Verifies successful creation of the article, validates its attributes, and ensures it is
    in the correct initial state and arix data are set.

    :param journal: An instance of the Journal to which the article belongs
    :param install_plugins: A callable to install necessary plugins for the operation
    :param user: An Account instance representing the article's owner
        an unsaved state
    :param arxiv_metadata: A callable to retrieve arxiv metadata
    :raises AssertionError: If article creation or validation of attributes fails
    """
    result, __ = arxiv_metadata("2504.10562v1")
    original_title = result["title"]
    result["title"] += "&<>"

    service = HandleArticleCreation(user, result, journal)
    article = service.run()
    assert article.pk
    assert article.journal == journal
    assert article.owner == user
    assert article.correspondence_author == user
    assert article.stage == STAGE_UNSUBMITTED
    assert article.current_step == 0
    assert article.title == original_title + "&amp;&lt;&gt;"
    assert article.abstract == result["abstract"]
    assert Identifier.objects.get(
        identifier="2504.10562v1",
        article=article,
        id_type="arxiv",
    )


@pytest.mark.django_db
def test_form_save_article_with_arxiv_id(
    journal: Journal, install_plugins: Callable, user: Account, arxiv_metadata: Callable, fake_request
):
    """
    Article created by ArxivMicroservice ignore the arxiv_id passed by the form to avoid arxiv_id inconsistencies.

    :param journal: An instance of the Journal to which the article belongs
    :param install_plugins: A callable to install necessary plugins for the operation
    :param user: An Account instance representing the article's owner
        an unsaved state
    :param arxiv_metadata: A callable to retrieve arxiv metadata
    :param fake_request: Test request object
    :raises AssertionError: If article creation or validation of attributes fails
    """
    result, __ = arxiv_metadata("2504.10562v1")

    service = HandleArticleCreation(user, result, journal)
    article = service.run()
    assert article.pk
    assert article.journal == journal
    assert article.owner == user
    assert article.correspondence_author == user
    assert article.stage == STAGE_UNSUBMITTED
    assert article.current_step == 0
    assert article.title == result["title"]
    assert article.abstract == result["abstract"]
    assert Identifier.objects.get(
        identifier="2504.10562v1",
        article=article,
        id_type="arxiv",
    )
    data = {
        "copyright_notice": True,
        "comments_editor": "AAA",
        "competing_interests": "AAA",
        "submission_requirements": True,
        "arxiv_article_id": article.pk,
        "arxiv_id": "2504.10562",
    }
    # enriching the current request that will be used by SubmissionStep1Form.trigger_submissionstart_event()
    # via get_current_request()
    GlobalRequestMiddleware.process_request(fake_request)
    form = SubmissionStep1Form(data=data, journal=journal, user=user, instance=article, step=1)
    assert form.is_valid()
    form.save()
    article.refresh_from_db()
    assert article.comments_editor == data["comments_editor"]
    assert article.competing_interests == data["competing_interests"]
    assert Identifier.objects.get(
        identifier="2504.10562v1",
        article=article,
        id_type="arxiv",
    )
    assert not Identifier.objects.filter(
        identifier="2504.10562",
        article=article,
        id_type="arxiv",
    ).exists()


@pytest.mark.parametrize("submission_step", [0, 1, 7, 8])
@pytest.mark.django_db
def test_double_arxiv_id_submission(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    arxiv_metadata: Callable,
    submission_step: int,
):
    """
    If a submitted article with a specific arxiv id exists, one cannot submit another article with the same id.

    If the article is unsubmitted, the same article is returned to continue the existing submission.

    :param journal: An instance of the Journal to which the article belongs
    :param install_plugins: A callable to install necessary plugins for the operation
    :param user: An Account instance representing the article's owner
        an unsaved state
    :param arxiv_metadata: A callable to retrieve arxiv metadata
    :param submission_step: Completed submission step
    :raises AssertionError: If article creation or validation of attributes fails
    """
    result, __ = arxiv_metadata("2504.10562v1")
    service = HandleArticleCreation(user, result, journal)
    article = service.run()
    assert Identifier.objects.get(
        identifier="2504.10562v1",
        article=article,
        id_type="arxiv",
    )
    article.current_step = submission_step
    if submission_step == 8:
        article.stage = STAGE_UNASSIGNED
    article.save()
    if submission_step == 8:
        with pytest.raises(ArXivIDAlreadyUsedError):
            ArXivToArticle(
                arxiv_id="2504.10562v1",
                journal=journal,
                user=user,
            ).run()
    elif submission_step == 0:
        arxiv_article = ArXivToArticle(
            arxiv_id="2504.10562v1",
            journal=journal,
            user=user,
        ).run()
        assert article != arxiv_article
        # and the "old" article has been deleted
        assert not Article.objects.filter(pk=article.pk).exists()

    else:
        with pytest.raises(ArXivIDContinueSubmissionError):
            arxiv_article = ArXivToArticle(
                arxiv_id="2504.10562v1",
                journal=journal,
                user=user,
            ).run()
