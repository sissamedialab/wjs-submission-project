"""
Tests for step1 cover-letter-file handling when the author revisits an already-submitted step 1.

Scenario under test: step 1 has already been submitted once (a cover letter *file* is already
attached), and the author goes back to step 1 and re-posts the form. Three variants, in both the
plain-submission form (:class:`SubmissionStep1Form`) and the revision form
(:class:`RevisionFullForm`, which shares its ``save()`` logic with ``RevisionConfirmForm``):

- the author does not touch the file field (no new upload, no "clear")
- the author checks "clear" to remove the existing file
- the author uploads a new file to replace the existing one

For each variant we check whether the *old* ``core.models.File`` row and its on-disk file are
removed, and whether re-posting without any change needlessly re-creates a new File.

Background (see ``docs/superpowers/specs/2026-09-16-step1-cover-letter-resubmission-fix.md`` for
the full analysis): Django's ``FileField.clean()`` returns the field's ``initial`` value - a
:class:`~plugins.wjs_submission.fields.CoreFileWrapper` around the existing file - whenever
nothing was uploaded and "clear" wasn't checked. That wrapper is truthy, so without special-casing
it, ``save()`` cannot tell "untouched" apart from "genuinely new upload". Both
``SubmissionStep1Form.save()`` and ``RevisionConfirmForm.save()`` now check for
``isinstance(value, CoreFileWrapper)`` explicitly and treat it as a true no-op; the plain-submission
form also deletes the previous file before saving a genuine replacement (mirroring what the
revision form already did), so no leftover ``File`` row/disk file is ever orphaned. The "clear"
case was already correct in both forms.
"""

import pathlib
from unittest.mock import patch

import pytest
from core import files as core_files
from core.models import Account, File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpRequest
from plugins.wjs_submission.models import RevisionStorage
from plugins.wjs_submission.step1.forms import RevisionFullForm, SubmissionStep1Form
from submission.models import Article

ORIGINAL_CONTENT = b"original cover letter content"
NEW_CONTENT = b"new cover letter content"


def _valid_step1_data(*, clear_file: bool = False) -> dict:
    """Build minimal valid POST data for step1 (all default SubmissionConfiguration flags are True)."""
    data = {
        "copyright_notice": True,
        "comments_editor": "Some comments to the editor",
        "competing_interests": "No competing interests",
        "submission_requirements": True,
    }
    if clear_file:
        data["cover_letter_file-clear"] = "on"
    return data


def _create_real_file(article: Article, owner: Account, *, filename: str, content: bytes) -> File:
    """Save a real file to disk/DB exactly as production code does, so File.delete() has something real to unlink."""
    file_obj = core_files.save_file_to_article(
        file_to_handle=SimpleUploadedFile(filename, content, content_type="application/pdf"),
        article=article,
        owner=owner,
        label="Cover letter",
    )
    file_obj.privacy = "owner"
    file_obj.save()
    return file_obj


def _attach_existing_cover_letter(article: Article, owner: Account) -> File:
    """Simulate an already-submitted step 1: article.submission_data already points at a real File."""
    existing_file = _create_real_file(article, owner, filename="original.pdf", content=ORIGINAL_CONTENT)
    article.submission_data.cover_letter_file = existing_file
    article.submission_data.save()
    return existing_file


def _make_revision_storage(article: Article, existing_file: File) -> RevisionStorage:
    """Simulate an already-submitted revision step 1: the draft file lives in RevisionStorage.data."""
    return RevisionStorage.objects.create(
        article=article,
        revision_flow_type=RevisionStorage.RevisionFlowType.FULL,
        data={"cover_letter_file": existing_file.pk},
    )


# --- Plain (first) submission: SubmissionStep1Form ---------------------------------------------


@pytest.mark.django_db
def test_submission_no_change_is_a_true_no_op(
    article: Article,
    author: Account,
    install_plugins,
    fake_request: HttpRequest,
):
    """
    Re-posting step1 untouched must not create a new File nor touch the existing one.

    The file input's initial value (a CoreFileWrapper around the existing file) is truthy, so
    Django's FileField.clean() returns it as the cleaned value even though nothing was uploaded.
    SubmissionStep1Form.save() special-cases CoreFileWrapper as "untouched" and leaves the
    existing File/pointer alone.
    """
    existing_file = _attach_existing_cover_letter(article, author)
    old_path = existing_file.self_article_path()
    assert pathlib.Path(old_path).exists(), "sanity check: setup must produce a real file on disk"

    form = SubmissionStep1Form(
        data=_valid_step1_data(),
        files=None,
        journal=article.journal,
        user=author,
        step=1,
        request=fake_request,
        instance=article,
        initial={},
    )
    assert form.is_valid(), form.errors

    with patch("plugins.wjs_submission.step1.forms.SubmissionStep1Form.trigger_submissionstart_event"):
        instance = form.save()
    instance.submission_data.refresh_from_db()

    assert instance.submission_data.cover_letter_file_id == existing_file.pk, "the pointer must be untouched"
    assert File.objects.filter(pk=existing_file.pk).exists(), "the existing File row must not be removed"
    assert pathlib.Path(old_path).exists(), "the existing on-disk file must not be removed"
    cover_letter_files = File.objects.filter(article_id=article.pk, label="Cover letter")
    assert list(cover_letter_files) == [existing_file], "no new cover-letter File row must be created"


@pytest.mark.django_db
def test_submission_clear_removes_the_file_row_and_the_disk_file(
    article: Article,
    author: Account,
    install_plugins,
    fake_request: HttpRequest,
):
    """Checking "clear" on an already-submitted step1 removes both the File row and the on-disk file."""
    existing_file = _attach_existing_cover_letter(article, author)
    old_path = existing_file.self_article_path()

    form = SubmissionStep1Form(
        data=_valid_step1_data(clear_file=True),
        files=None,
        journal=article.journal,
        user=author,
        step=1,
        request=fake_request,
        instance=article,
        initial={},
    )
    assert form.is_valid(), form.errors

    with patch("plugins.wjs_submission.step1.forms.SubmissionStep1Form.trigger_submissionstart_event"):
        instance = form.save()
    instance.submission_data.refresh_from_db()

    assert instance.submission_data.cover_letter_file is None, "the pointer must be cleared"
    assert not File.objects.filter(pk=existing_file.pk).exists(), "the old File row must be removed"
    assert not pathlib.Path(old_path).exists(), "the old on-disk file must be removed"


@pytest.mark.django_db
def test_submission_new_upload_replaces_the_pointer_and_removes_the_old_file(
    article: Article,
    author: Account,
    install_plugins,
    fake_request: HttpRequest,
):
    """Uploading a genuinely new file replaces the pointer, and the previous file is cleaned up."""
    existing_file = _attach_existing_cover_letter(article, author)
    old_path = existing_file.self_article_path()

    files = {"cover_letter_file": SimpleUploadedFile("new.pdf", NEW_CONTENT, content_type="application/pdf")}
    form = SubmissionStep1Form(
        data=_valid_step1_data(),
        files=files,
        journal=article.journal,
        user=author,
        step=1,
        request=fake_request,
        instance=article,
        initial={},
    )
    assert form.is_valid(), form.errors

    with patch("plugins.wjs_submission.step1.forms.SubmissionStep1Form.trigger_submissionstart_event"):
        instance = form.save()
    instance.submission_data.refresh_from_db()
    new_file = instance.submission_data.cover_letter_file

    assert new_file.pk != existing_file.pk, "a new File row must be created for the new upload"
    content = pathlib.Path(new_file.self_article_path()).read_bytes()
    assert content == NEW_CONTENT, "the new file's content must be the uploaded content"

    assert not File.objects.filter(pk=existing_file.pk).exists(), "the old File row must be removed"
    assert not pathlib.Path(old_path).exists(), "the old on-disk file must be removed"


# --- Full revision: RevisionFullForm (shares save() with RevisionConfirmForm) -------------------
#
# The revision draft file lives in RevisionStorage.data["cover_letter_file"] (a File pk), not on
# article.submission_data - RevisionConfirmForm (parent of RevisionFullForm) rebuilds the field's
# initial value from RevisionStorage itself.


@pytest.mark.django_db
def test_revision_no_change_is_a_true_no_op(
    article: Article,
    author: Account,
    install_plugins,
    fake_request: HttpRequest,
):
    """
    Re-posting revision step1 untouched must not recreate the file nor touch the existing one.

    Same root cause as the plain-submission case (initial CoreFileWrapper is truthy so
    FileField.clean() returns it instead of None), but RevisionConfirmForm.save() now
    special-cases CoreFileWrapper as "untouched" and leaves RevisionStorage.data alone.
    """
    existing_file = _create_real_file(article, author, filename="original.pdf", content=ORIGINAL_CONTENT)
    revision_storage = _make_revision_storage(article, existing_file)
    old_path = existing_file.self_article_path()
    assert pathlib.Path(old_path).exists(), "sanity check: setup must produce a real file on disk"

    form = RevisionFullForm(
        data=_valid_step1_data(),
        files=None,
        journal=article.journal,
        user=author,
        step=1,
        request=fake_request,
        instance=article,
    )
    assert form.is_valid(), form.errors

    form.save()
    revision_storage.refresh_from_db()

    assert revision_storage.data["cover_letter_file"] == existing_file.pk, "the storage pointer must be untouched"
    assert File.objects.filter(pk=existing_file.pk).exists(), "the existing File row must not be removed"
    assert pathlib.Path(old_path).exists(), "the existing on-disk file must not be removed"
    cover_letter_files = File.objects.filter(article_id=article.pk, label="Cover letter")
    assert list(cover_letter_files) == [existing_file], "no new cover-letter File row must be created"


@pytest.mark.django_db
def test_revision_clear_removes_the_file_row_and_the_disk_file(
    article: Article,
    author: Account,
    install_plugins,
    fake_request: HttpRequest,
):
    """Checking "clear" during revision removes the old File row/disk file and drops the storage key."""
    existing_file = _create_real_file(article, author, filename="original.pdf", content=ORIGINAL_CONTENT)
    revision_storage = _make_revision_storage(article, existing_file)
    old_path = existing_file.self_article_path()

    form = RevisionFullForm(
        data=_valid_step1_data(clear_file=True),
        files=None,
        journal=article.journal,
        user=author,
        step=1,
        request=fake_request,
        instance=article,
    )
    assert form.is_valid(), form.errors

    form.save()
    revision_storage.refresh_from_db()

    assert "cover_letter_file" not in revision_storage.data, "the storage key must be dropped"
    assert not File.objects.filter(pk=existing_file.pk).exists(), "the old File row must be removed"
    assert not pathlib.Path(old_path).exists(), "the old on-disk file must be removed"


@pytest.mark.django_db
def test_revision_new_upload_replaces_the_file_and_cleans_up_the_old_one(
    article: Article,
    author: Account,
    install_plugins,
    fake_request: HttpRequest,
):
    """Uploading a genuinely new file during revision replaces the old one, with no orphan left behind."""
    existing_file = _create_real_file(article, author, filename="original.pdf", content=ORIGINAL_CONTENT)
    revision_storage = _make_revision_storage(article, existing_file)
    old_path = existing_file.self_article_path()

    files = {"cover_letter_file": SimpleUploadedFile("new.pdf", NEW_CONTENT, content_type="application/pdf")}
    form = RevisionFullForm(
        data=_valid_step1_data(),
        files=files,
        journal=article.journal,
        user=author,
        step=1,
        request=fake_request,
        instance=article,
    )
    assert form.is_valid(), form.errors

    form.save()
    revision_storage.refresh_from_db()
    new_file_id = revision_storage.data["cover_letter_file"]

    assert new_file_id != existing_file.pk, "a new File row must be created for the new upload"
    assert not File.objects.filter(pk=existing_file.pk).exists(), "the old File row must be removed"
    assert not pathlib.Path(old_path).exists(), "the old on-disk file must be removed"

    new_file = File.objects.get(pk=new_file_id)
    content = pathlib.Path(new_file.self_article_path()).read_bytes()
    assert content == NEW_CONTENT, "the new file's content must be the uploaded content"
