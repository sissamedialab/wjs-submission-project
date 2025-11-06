from collections.abc import Callable
from itertools import product
from unittest.mock import patch

import pytest
from core.models import Account, Country
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from journal.models import Journal
from plugins.wjs_submission.access_mode import AccessModeConfiguration, get_access_mode_configuration
from plugins.wjs_submission.events import SubmissionEvent
from plugins.wjs_submission.models import AccessMode, ArticleSubmission
from plugins.wjs_submission.settings import OA_CODE
from plugins.wjs_submission.step1.forms import SubmissionStep1Form
from plugins.wjs_submission.step5.forms import SubmissionStep5Form
from plugins.wjs_submission.step6.forms import SubmissionStep6Form
from plugins.wjs_submission.step7.forms import SubmissionStep7Form
from pytest_django.asserts import assertQuerysetEqual
from submission.models import Article, Licence


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


@pytest.mark.parametrize(
    ("cas", "das"),
    list(product(ArticleSubmission.CasDeclaration.values, ArticleSubmission.DasDeclaration.values)),
)
@pytest.mark.django_db
def test_cas_das_url_form(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
    fake_request,
    cas: bool,
    das: bool,
):
    data = {
        "das": das,
        "das_url": "http://example.com" if das == "url" else "",
        "cas": cas,
        "cas_url": "http://example.com" if cas == "url" else "",
    }
    form = SubmissionStep6Form(data=data, journal=journal, instance=article, step=6, initial={})
    assert form.is_valid()
    instance = form.save()
    assert instance.submission_data.cas == cas
    assert instance.submission_data.das == das


@pytest.mark.parametrize(
    ("cas", "das"),
    list(product(ArticleSubmission.CasDeclaration.values, ArticleSubmission.DasDeclaration.values)),
)
@pytest.mark.django_db
def test_cas_das_url_error_form(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
    fake_request,
    cas: bool,
    das: bool,
):
    data = {
        "das": das,
        "cas": cas,
    }
    form = SubmissionStep6Form(data=data, journal=journal, instance=article, step=6, initial={})
    if das == "url" or cas == "url":
        assert not form.is_valid()
    else:
        assert form.is_valid()
        instance = form.save()
        assert instance.submission_data.cas == cas
        assert instance.submission_data.das == das


@pytest.mark.parametrize(
    "access_mode_fixed",
    [
        True,
        False,
    ],
)
@pytest.mark.django_db
def test_access_mode_form(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
    fake_request,
    access_mode_fixed: bool,
):
    """
    Form is configured according to the access mode calculated by article country.
    """
    with (
        patch("plugins.wjs_submission.access_mode.ACCESS_MODE_COUNTRIES") as ACCESS_MODE_COUNTRIES,  # noqa: N806
        patch("plugins.wjs_submission.access_mode.ACCESS_MODE_CONTROL_FUNCTION") as ACCESS_MODE_CONTROL_FUNCTION,  # noqa: N806
    ):
        ACCESS_MODE_CONTROL_FUNCTION.get.return_value = (
            "plugins.wjs_submission.access_mode.get_oa_transformative_agreement"
        )
        ACCESS_MODE_COUNTRIES.get.return_value = ["fr", "it", "gb"]
        if access_mode_fixed:
            country, __ = Country.objects.get_or_create(code="it", name="Italy")
        else:
            country, __ = Country.objects.get_or_create(code="ru", name="Russia")
        article.submission_data.affiliation_country = country
        article.submission_data.save()
        configuration = get_access_mode_configuration(user, article)
        form = SubmissionStep7Form(
            journal=journal,
            instance=article,
            step=7,
            configuration=configuration,
            initial={},
        )
        if access_mode_fixed:
            assert not configuration.is_default
            assert isinstance(form.fields["license"].widget, forms.HiddenInput)
            assert isinstance(form.fields["rights"].widget, forms.HiddenInput)
            assert isinstance(form.fields["access_mode"].widget, forms.HiddenInput)
            assertQuerysetEqual(
                form.fields["access_mode"].queryset,
                AccessMode.objects.filter(parameters__journal=article.journal, user_selectable=False),
            )
            assert form.initial["access_mode"] == configuration.access_mode
            assert form.initial["rights"] == configuration.copyright_text
            assert form.initial["license"] == configuration.license
        else:
            assert configuration.is_default
            assert isinstance(form.fields["rights"].widget, forms.HiddenInput)
            assertQuerysetEqual(
                form.fields["access_mode"].queryset,
                AccessMode.objects.filter(parameters__journal=article.journal, user_selectable=True),
            )
            assert form.initial["access_mode"] == configuration.access_mode
            assert form.initial["rights"] == configuration.copyright_text
            assert form.initial["license"] == configuration.license


@pytest.mark.parametrize(
    "access_mode_fixed",
    [
        True,
        False,
    ],
)
@pytest.mark.django_db
def test_access_mode_form_data(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
    fake_request,
    access_mode_fixed: bool,
):
    """
    Values derived from access mode configuration are preserved on submission and stored in the submission data.

    Event is also raised.
    """
    with patch("plugins.wjs_submission.step7.forms.events_logic.Events.raise_event") as raise_event:
        oa = AccessMode.objects.get(code=OA_CODE)
        other = AccessMode.objects.exclude(code=OA_CODE).first()
        licence = Licence.objects.create(short_name="random", name="Random", journal=journal)
        journal_parameters = oa.parameters.get(journal=article.journal)

        if access_mode_fixed:
            configuration = AccessModeConfiguration(
                access_mode=oa,
                license=journal_parameters.licence,
                copyright_text=journal_parameters.copyright,
                is_default=False,
            )
        else:
            configuration = AccessModeConfiguration(
                access_mode=oa,
                license=journal_parameters.licence,
                copyright_text=journal_parameters.copyright,
                is_default=True,
            )
        form = SubmissionStep7Form(
            data={
                "license": licence,
                "rights": "random text",
                "access_mode": other,
            },
            journal=journal,
            instance=article,
            step=7,
            configuration=configuration,
            initial={},
        )
        if access_mode_fixed:
            form.is_valid()
            assert form.cleaned_data["access_mode"] == configuration.access_mode
            assert form.cleaned_data["rights"] == configuration.copyright_text
            assert form.cleaned_data["license"] == configuration.license
        else:
            form.is_valid()
            assert form.cleaned_data["access_mode"] == other
            assert form.cleaned_data["rights"] == "random text"
            assert form.cleaned_data["license"] == licence
        form.save()
        article.refresh_from_db()
        article.submission_data.refresh_from_db()
        if access_mode_fixed:
            assert article.submission_data.access_mode == configuration.access_mode
            assert article.rights == configuration.copyright_text
            assert article.license == configuration.license
        else:
            assert article.submission_data.access_mode == other
            assert article.rights == "random text"
            assert article.license == licence
        raise_event.assert_called_once_with(
            SubmissionEvent.ON_ACCESS_MODE_SELECTION, article=article, submission_data=article.submission_data
        )
