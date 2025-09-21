from collections.abc import Callable

import pytest
from core.models import Account
from django.core.files.uploadedfile import SimpleUploadedFile
from journal.models import Journal
from plugins.wjs_submission.step1.forms import SubmissionStep1Form
from plugins.wjs_submission.step5.forms import SubmissionStep5Form
from submission.models import Article


@pytest.mark.parametrize(
    ("enabled", "selected"),
    [
        (
            True,
            False,
        ),
        (
            True,
            True,
        ),
        (
            False,
            True,
        ),
        (
            False,
            False,
        ),
    ],
)
@pytest.mark.django_db
def test_clean_copyright_notice(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    enabled: bool,
    selected: bool,
):
    journal.submissionconfiguration.copyright_notice = enabled
    journal.submissionconfiguration.save()
    data = {
        "copyright_notice": selected,
        "comments_editor": "AAA",
        "competing_interests": "AAA",
        "submission_requirements": True,
    }
    form = SubmissionStep1Form(data=data, journal=journal, user=user, step=1)
    if enabled and not selected:
        assert not form.is_valid()
        assert form.errors == {"copyright_notice": ["This field is required."]}
    else:
        assert form.is_valid()


@pytest.mark.parametrize(("extension", "is_valid"), [("jpg", False), ("pdf", True)])
@pytest.mark.django_db
def test_save_cover_letter_permission(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    extension: str,
    is_valid: bool,
):
    """
    Cover letter file is saved with the correct privacy setting and its extension is validated.

    :param journal: Instance of the `Journal` model used in the test.
    :type journal: Journal
    :param install_plugins: Callable used to set up any required plugins for the test.
    :type install_plugins: Callable
    :param user: Instance of the `Account` model representing the user interacting with the
                 submission form.
    :type user: Account
    :param extension: File extension of the uploaded cover letter to be tested, e.g., "jpg", "pdf".
    :type extension: str
    :param is_valid: Boolean indicating whether the form validation is expected to pass. True
                     for valid extensions, False otherwise.
    :type is_valid: bool
    :raises AssertionError: If the actual outcomes (validation, errors, and saved data) do
                            not match the expected outcomes defined in the test.
    """
    data = {
        "copyright_notice": True,
        "comments_editor": "AAA",
        "competing_interests": "AAA",
        "submission_requirements": True,
    }
    files = {"cover_letter_file": SimpleUploadedFile(f"file.{extension}", b"file_content", content_type="image/jpeg")}
    form = SubmissionStep1Form(data=data, journal=journal, user=user, files=files, step=1)
    if not is_valid:
        assert not form.is_valid()
        assert form.errors == {"cover_letter_file": ["File extension not allowed."]}
    else:
        assert form.is_valid()
        article = form.save()
        assert article
        assert article.submission_data.cover_letter_file
        assert article.submission_data.cover_letter_file.privacy == "owner"


@pytest.mark.parametrize(
    ("enabled", "selected"),
    [
        (
            True,
            False,
        ),
        (
            True,
            True,
        ),
        (
            False,
            True,
        ),
        (
            False,
            False,
        ),
    ],
)
@pytest.mark.django_db
def test_clean_submission_requirements(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    enabled: bool,
    selected: bool,
):
    journal.submissionconfiguration.submission_check = enabled
    journal.submissionconfiguration.save()
    data = {
        "copyright_notice": True,
        "comments_editor": "AAA",
        "competing_interests": "AAA",
        "submission_requirements": selected,
    }
    form = SubmissionStep1Form(data=data, journal=journal, user=user, step=1)
    if enabled and not selected:
        assert not form.is_valid()
        assert form.errors == {"submission_requirements": ["This field is required."]}
    else:
        assert form.is_valid()


@pytest.mark.parametrize(
    ("text", "file"),
    [
        (
            True,
            False,
        ),
        (
            True,
            True,
        ),
        (
            False,
            True,
        ),
        (
            False,
            False,
        ),
    ],
)
@pytest.mark.django_db
def test_clean_comments_editor_requirements(
    journal: Journal, install_plugins: Callable, user: Account, text: bool, file: bool
):
    journal.submissionconfiguration.comments_to_the_editor = True
    journal.submissionconfiguration.save()
    data = {
        "copyright_notice": True,
        "comments_editor": "",
        "competing_interests": "XXX",
        "submission_requirements": "AAA",
    }
    files = None
    if text:
        data["comments_editor"] = "AAA"
    if file:
        files = {"cover_letter_file": SimpleUploadedFile("file.docx", b"file_content", content_type="image/jpeg")}
    form = SubmissionStep1Form(data=data, journal=journal, user=user, files=files, step=1)
    assert form.is_valid() is (file or text)
    if not (file or text):
        assert form.errors == {"comments_editor": ["You must enter a cover letter or upload a file to proceed."]}
    else:
        assert form.errors == {}


@pytest.mark.parametrize(
    ("language", "section"),
    [
        (
            True,
            False,
        ),
        (
            True,
            True,
        ),
        (
            False,
            True,
        ),
        (
            False,
            False,
        ),
    ],
)
@pytest.mark.django_db
def test_edit_metadata_form(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
    fake_request,
    language: bool,
    section: bool,
):
    journal.submissionconfiguration.license = False
    journal.submissionconfiguration.language = language
    journal.submissionconfiguration.section = section
    journal.submissionconfiguration.default_section = journal.section_set.last()
    journal.submissionconfiguration.default_language = "eng"
    journal.submissionconfiguration.save()
    data = {"title": "<script>title</script>&<>", "abstract": "<b>abstract</b>&<>"}
    if language:
        data["language"] = "fra"
    if section:
        data["section"] = journal.section_set.first().pk
    form = SubmissionStep5Form(data=data, journal=journal, instance=article, step=5)
    if section:
        assert "section" in form.fields
    else:
        assert "section" not in form.fields
    if language:
        assert "language" in form.fields
    else:
        assert "language" not in form.fields
    assert form.is_valid()
    instance = form.save(request=fake_request)
    if language:
        assert instance.language == "fra"
    else:
        assert instance.language == journal.submissionconfiguration.default_language
    if section:
        assert instance.section == journal.section_set.first()
    else:
        assert instance.section == journal.submissionconfiguration.default_section
    assert instance.title == "title&amp;&lt;&gt;"
    assert instance.abstract == "<b>abstract</b>&amp;&lt;&gt;"
