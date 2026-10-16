"""Tests for the affiliation field of the ArticleSubmission advanced admin (specs#3131)."""

import pytest
from core.models import ControlledAffiliation
from plugins.wjs_submission.advanced_admin.advanced_admin import ArticleSubmissionAdmin
from plugins.wjs_submission.advanced_admin.forms import ArticleSubmissionAdminForm
from plugins.wjs_submission.models import ArticleSubmission


def _submission(article) -> ArticleSubmission:
    submission, __ = ArticleSubmission.objects.get_or_create(article=article)
    return submission


def _form_data(submission: ArticleSubmission, affiliation: ControlledAffiliation | None) -> dict:
    """Bound data for the admin form, leaving every other field as it is."""
    return {
        "cover_letter_file": "",
        "access_mode": submission.access_mode_id or "",
        "special_request": submission.special_request,
        "affiliation": affiliation.pk if affiliation else "",
    }


@pytest.mark.django_db
def test_affiliation_is_an_admin_field():
    """The EO sees the affiliation in the ArticleSubmission advanced admin."""
    assert "affiliation" in ArticleSubmissionAdmin.fields, "affiliation must be editable in the admin"


@pytest.mark.django_db
def test_affiliation_choices_are_correspondence_author_affiliations(article, author, coauthor):
    """Choices are limited to the correspondence author's affiliations."""
    form = ArticleSubmissionAdminForm(instance=_submission(article))
    choices = set(form.fields["affiliation"].queryset)
    assert choices == set(author.affiliations), "Only the correspondence author's affiliations"
    assert not choices & set(coauthor.affiliations), "Other accounts' affiliations must not be offered"


@pytest.mark.django_db
def test_other_account_affiliation_is_rejected(article, coauthor):
    """An affiliation of another account cannot be saved."""
    submission = _submission(article)
    form = ArticleSubmissionAdminForm(data=_form_data(submission, coauthor.affiliations.first()), instance=submission)
    assert not form.is_valid(), "Another account's affiliation must be rejected"
    assert "affiliation" in form.errors, "The error must be on the affiliation field"


@pytest.mark.django_db
def test_saving_sets_affiliation_and_keeps_access_mode(article, author):
    """Saving stores the affiliation and does not touch access mode, licence and copyright."""
    submission = _submission(article)
    access_mode_before = submission.access_mode_id
    license_before = article.license_id
    rights_before = article.rights
    affiliation = author.affiliations.first()

    form = ArticleSubmissionAdminForm(data=_form_data(submission, affiliation), instance=submission)
    assert form.is_valid(), form.errors
    form.save()

    submission.refresh_from_db()
    article.refresh_from_db()
    assert submission.affiliation == affiliation, "The affiliation must be stored"
    assert submission.access_mode_id == access_mode_before, "Access mode must not be recomputed"
    assert article.license_id == license_before, "Licence must not change"
    assert article.rights == rights_before, "Copyright must not change"


@pytest.mark.django_db
def test_stored_affiliation_outside_author_stays_valid(article, coauthor):
    """A stored affiliation no longer belonging to the correspondence author does not block saving."""
    submission = _submission(article)
    stale_affiliation = coauthor.affiliations.first()
    submission.affiliation = stale_affiliation
    submission.save()

    form = ArticleSubmissionAdminForm(data=_form_data(submission, stale_affiliation), instance=submission)
    assert stale_affiliation in form.fields["affiliation"].queryset, "Stored affiliation must stay selectable"
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_form_valid_without_correspondence_author(article):
    """With no correspondence author there are no choices, and the form still validates."""
    article.correspondence_author = None
    article.save()
    submission = _submission(article)

    form = ArticleSubmissionAdminForm(data=_form_data(submission, None), instance=submission)
    assert not form.fields["affiliation"].queryset.exists(), "No affiliation to offer"
    assert form.is_valid(), form.errors
