from collections.abc import Callable
from datetime import timedelta
from itertools import product
from unittest.mock import patch

import pytest
from core.models import Account, Country
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpRequest, QueryDict
from django.urls import reverse
from django.utils.timezone import now
from events import logic as event_logic
from journal.models import ArticleOrdering, Issue, IssueType, Journal
from plugins.wjs_submission import settings
from plugins.wjs_submission.access_mode import AccessModeConfiguration, get_access_mode_configuration
from plugins.wjs_submission.models import AccessMode, ArticleSubmission, RevisionStorage
from plugins.wjs_submission.settings import OA_CODE
from plugins.wjs_submission.step1.forms import RevisionConfirmForm, RevisionFullForm, SubmissionStep1Form
from plugins.wjs_submission.step2.forms import SubmissionStep2Form
from plugins.wjs_submission.step3.forms import SubmissionStep3Form
from plugins.wjs_submission.step4.forms import AddCollaborationForm
from plugins.wjs_submission.step5.forms import SubmissionStep5Form
from plugins.wjs_submission.step6.forms import SubmissionStep6Form
from plugins.wjs_submission.step7.forms import RevisionStep7Form, SubmissionStep7Form
from plugins.wjs_submission.step8.forms import SubmissionStep8Form
from pytest_django.asserts import assertQuerySetEqual
from submission.models import Article, Field, Keyword, KeywordArticle, KeywordGroup, Licence


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
    fake_request: HttpRequest,
):
    journal.submissionconfiguration.copyright_notice = enabled
    journal.submissionconfiguration.save()
    data = {
        "copyright_notice": selected,
        "comments_editor": "AAA",
        "competing_interests": "AAA",
        "submission_requirements": True,
    }
    form = SubmissionStep1Form(data=data, journal=journal, user=user, step=1, request=fake_request)
    if enabled and not selected:
        assert not form.is_valid()
        assert form.errors == {"copyright_notice": ["This field is required."]}
    else:
        assert form.is_valid()


@pytest.mark.parametrize(
    ("selected", "result"),
    [
        (
            True,
            True,
        ),
        (
            False,
            False,
        ),
    ],
)
@pytest.mark.django_db
def test_save_use_of_ai_flag(
    journal: Journal, install_plugins: Callable, user: Account, selected: bool, result: bool, fake_request
):
    """Setting Use of AI custom field updates ArticleSubmission.use_of_ai_flag as well."""
    data = {
        settings.USE_OF_AI_FIELD_LABEL: "Something" if selected else "",
        "copyright_notice": True,
        "comments_editor": "AAA",
        "competing_interests": "AAA",
        "submission_requirements": True,
    }
    Field.objects.create(
        journal=journal,
        name=settings.USE_OF_AI_FIELD_LABEL,
        kind="text",
        order=1,
        help_text="Hello",
        required=False,
        display=True,
    )
    with patch("plugins.wjs_submission.step1.forms.SubmissionStep1Form.trigger_submissionstart_event"):
        form = SubmissionStep1Form(data=data, journal=journal, user=user, step=1, request=fake_request)
        assert form.is_valid()
        instance = form.save()
        assert instance.submission_data.use_of_ai_flag is result


@pytest.mark.parametrize(("extension", "is_valid"), [("jpg", False), ("pdf", True)])
@pytest.mark.django_db
def test_save_cover_letter_permission(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    extension: str,
    is_valid: bool,
    # a request is needed by Janeway's events.logic.on_article_submission_start upon form.save()
    # (because of event ON_ARTICLE_SUBMISSION_START)
    fake_request: HttpRequest,
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
    fake_request.user = user
    files = {"cover_letter_file": SimpleUploadedFile(f"file.{extension}", b"file_content", content_type="image/jpeg")}
    form = SubmissionStep1Form(data=data, journal=journal, user=user, files=files, step=1, request=fake_request)
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
    fake_request: HttpRequest,
):
    journal.submissionconfiguration.submission_check = enabled
    journal.submissionconfiguration.save()
    data = {
        "copyright_notice": True,
        "comments_editor": "AAA",
        "competing_interests": "AAA",
        "submission_requirements": selected,
    }
    form = SubmissionStep1Form(data=data, journal=journal, user=user, step=1, request=fake_request)
    if enabled and not selected:
        assert not form.is_valid()
        assert form.errors == {"submission_requirements": ["This field is required."]}
    else:
        assert form.is_valid()


@pytest.mark.parametrize("comments_to_the_editor", [True, False])
@pytest.mark.parametrize(
    "revision_flow_type",
    [RevisionStorage.RevisionFlowType.FULL, RevisionStorage.RevisionFlowType.CONFIRM],
)
@pytest.mark.django_db
def test_revision_requires_cover_letter_whatever_the_journal_setting(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
    fake_request: HttpRequest,
    comments_to_the_editor: bool,
    revision_flow_type: str,
):
    """
    A full or confirm revision always needs a cover letter text or file, like the browser already requires.

    The server used to check it only when the journal enables the comments to the editor in the submission.
    """
    journal.submissionconfiguration.comments_to_the_editor = comments_to_the_editor
    journal.submissionconfiguration.save()
    RevisionStorage.objects.create(article=article, revision_flow_type=revision_flow_type, data={})
    form_class = (
        RevisionFullForm if revision_flow_type == RevisionStorage.RevisionFlowType.FULL else RevisionConfirmForm
    )
    form = form_class(
        data={
            "copyright_notice": True,
            "comments_editor": "",
            "competing_interests": "XXX",
            "submission_requirements": True,
        },
        journal=journal,
        user=user,
        step=1,
        request=fake_request,
        instance=article,
    )
    assert not form.is_valid()
    assert set(form.errors) == {"comments_editor", "cover_letter_file"}


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
    journal: Journal, install_plugins: Callable, user: Account, text: bool, file: bool, fake_request: HttpRequest
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
    form = SubmissionStep1Form(data=data, journal=journal, user=user, files=files, step=1, request=fake_request)
    assert form.is_valid() is (file or text)
    if not (file or text):
        assert form.errors == {
            "comments_editor": ["You must enter a cover letter or upload a file to proceed."],
            "cover_letter_file": ["You must enter a cover letter or upload a file to proceed."],
        }
    else:
        assert form.errors == {}


@pytest.mark.django_db
def test_step1_form_unsaved_article_with_comments_to_the_editor_disabled(
    journal: Journal, install_plugins: Callable, user: Account, fake_request: HttpRequest
):
    """
    Regression test for Django 5.2: constructing the form must not raise on an unsaved Article.

    ``comments_to_the_editor = False`` is required to reach the ``or`` branch at
    step1/forms.py:129-133 that calls ``is_revision_full``/``is_revision_confirm`` on
    ``self.instance`` — an unsaved ``Article()`` when no ``instance=`` is passed in, as happens on
    step 1 of a first-time submission. On Django 5.x, ``is_revision_confirm``/``is_revision_full``
    (and ``is_revision_metadata``) used to raise ``ValueError`` when looking up
    ``RevisionStorage.objects.get(article=<unsaved instance>)`` because Django model instances are
    always truthy, so their ``if not article:`` guard never caught the unsaved instance.
    """
    journal.submissionconfiguration.comments_to_the_editor = False
    journal.submissionconfiguration.save()
    data = {
        "copyright_notice": True,
        "comments_editor": "AAA",
        "competing_interests": "AAA",
        "submission_requirements": True,
    }
    form = SubmissionStep1Form(data=data, journal=journal, user=user, step=1, request=fake_request)
    assert form.instance.pk is None, "This test only covers the unsaved-instance (new submission) code path."
    assert form.is_valid(), f"Form should be valid, got errors: {form.errors}"


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
        "current_step": 6,
    }
    form = SubmissionStep6Form(data=data, journal=journal, instance=article, step=6, initial={})
    form.is_valid()
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
        "current_step": 6,
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
        ACCESS_MODE_COUNTRIES.get.return_value = ["FR", "IT", "GB"]
        if access_mode_fixed:
            country, __ = Country.objects.get_or_create(code="IT", name="Italy")
        else:
            country, __ = Country.objects.get_or_create(code="RU", name="Russia")
        location = user.primary_affiliation().organization.locations.first()
        location.country = country
        location.save()
        article.submission_data.affiliation = user.primary_affiliation()
        article.submission_data.save()
        configuration = get_access_mode_configuration(user, article)
        form = SubmissionStep7Form(
            journal=journal,
            instance=article,
            step=7,
            configuration=configuration,
            initial={},
        )
        assert "license" not in form.fields, "license follows from the access mode, the form does not handle it"
        assert "rights" not in form.fields, "rights follow from the access mode, the form does not handle them"
        assert form.initial["access_mode"] == configuration.access_mode
        if access_mode_fixed:
            assert not configuration.user_can_select_access_mode
            assert isinstance(form.fields["access_mode"].widget, forms.HiddenInput)
            assertQuerySetEqual(
                form.fields["access_mode"].queryset,
                AccessMode.objects.filter(parameters__journal=article.journal, user_selectable=False),
            )
        else:
            assert configuration.user_can_select_access_mode
            assertQuerySetEqual(
                form.fields["access_mode"].queryset,
                AccessMode.objects.filter(parameters__journal=article.journal, user_selectable=True),
            )


@pytest.mark.parametrize(
    "access_mode_fixed",
    [
        True,
        False,
        None,
    ],
)
@pytest.mark.django_db
def test_access_mode_form_data(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
    fake_request,
    access_mode_fixed: bool | None,
):
    """
    The access mode is forced or chosen by the user and stored in the submission data, license and rights follow.
    """
    oa = AccessMode.objects.get(code=OA_CODE)
    other = AccessMode.objects.exclude(code=OA_CODE).first()
    oa_parameters = oa.parameters.get(journal=article.journal)
    other_parameters = other.parameters.get(journal=article.journal)
    article.rights = "original rights"
    article.save()
    original_license = article.license

    if access_mode_fixed is None:
        configuration = None
        data = {}
    else:
        configuration = AccessModeConfiguration(
            access_mode=oa,
            license=oa_parameters.licence,
            copyright_text=oa_parameters.copyright,
            user_can_select_access_mode=not access_mode_fixed,
        )
        data = {"access_mode": other}
    form = SubmissionStep7Form(
        data=data,
        journal=journal,
        instance=article,
        step=7,
        configuration=configuration,
        initial={},
    )
    assert form.is_valid(), form.errors
    form.save()
    article.refresh_from_db()
    article.submission_data.refresh_from_db()
    if access_mode_fixed is True:
        assert article.submission_data.access_mode == oa, "the submitted access mode is ignored"
        assert article.license == oa_parameters.licence
        assert article.rights == oa_parameters.copyright
    elif access_mode_fixed is False:
        assert article.submission_data.access_mode == other
        assert article.license == other_parameters.licence
        assert article.rights == other_parameters.copyright
    else:
        assert not article.submission_data.access_mode
        assert article.license == original_license, "without configuration license is not wiped"
        assert article.rights == "original rights", "without configuration rights are not wiped"


@pytest.mark.django_db
def test_step7_form_open_access_article_is_not_treated_as_a_correction(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
):
    """
    A normal article with the access mode used for corrections still gets the preset licence and rights.

    Open access is the correction access mode of every journal without a specific setting (e.g. JCOM): being open
    access does not make an article a correction.
    """
    oa = AccessMode.objects.get(code=OA_CODE)
    preset = oa.parameters.get(journal=journal)
    article.rights = "custom rights"
    article.save()
    with patch("plugins.wjs_submission.access_mode.CORRECTION_ACCESS_MODE_CODE", {None: OA_CODE}):
        configuration = AccessModeConfiguration(
            access_mode=oa, license=preset.licence, copyright_text=preset.copyright, user_can_select_access_mode=True
        )
        form = SubmissionStep7Form(
            data={"access_mode": oa.pk},
            journal=journal,
            instance=article,
            step=7,
            configuration=configuration,
            initial={},
        )
        assert form.is_valid(), form.errors
        form.save()
    article.refresh_from_db()
    assert article.license == preset.licence
    assert article.rights == preset.copyright
    assert not article.submission_data.license_override
    assert not article.submission_data.rights_override


@pytest.mark.django_db
def test_step7_form_unchanged_revision_offers_only_stored_access_mode(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
):
    """
    A revision keeping author and affiliation offers only the stored access mode, even if authors cannot choose it.
    """
    stored = AccessMode.objects.exclude(code=OA_CODE).first()
    stored.user_selectable = False
    stored.save()
    article.submission_data.affiliation = user.primary_affiliation()
    article.submission_data.access_mode = stored
    article.submission_data.save()
    RevisionStorage.objects.create(
        article=article,
        revision_flow_type=RevisionStorage.RevisionFlowType.FULL,
        data={
            "correspondence_author": article.correspondence_author.pk,
            "affiliation_pk": article.submission_data.affiliation_id,
            "access_mode": stored.pk,
        },
    )
    configuration = get_access_mode_configuration(user, article)
    form = RevisionStep7Form(
        journal=journal,
        instance=article,
        step=7,
        configuration=configuration,
        revision_full=True,
        initial={},
    )
    assert not configuration.user_can_select_access_mode
    assertQuerySetEqual(form.fields["access_mode"].queryset, AccessMode.objects.filter(pk=stored.pk))


@pytest.mark.parametrize("affiliation_changed", [False, True])
@pytest.mark.django_db
def test_revision_access_mode_recalculated_only_if_author_or_affiliation_change(
    journal: Journal,
    install_plugins: Callable,
    user: Account,
    article: Article,
    affiliation_changed: bool,
):
    """
    Access mode, license and rights are preserved in a revision without author and affiliation changes.

    If the corresponding author or the affiliation change, the access mode is recalculated by the standard rules.
    """
    oa = AccessMode.objects.get(code=OA_CODE)
    other = AccessMode.objects.exclude(code=OA_CODE).first()
    licence = Licence.objects.create(short_name="original", name="Original", journal=journal)
    article.license = licence
    article.rights = "original rights"
    article.save()
    article.submission_data.affiliation = user.primary_affiliation()
    # access mode, license and rights changed by the EO
    article.submission_data.access_mode = other
    article.submission_data.license_override = True
    article.submission_data.rights_override = True
    article.submission_data.save()
    journal_parameters = oa.parameters.get(journal=journal)
    calculated = AccessModeConfiguration(
        access_mode=oa,
        license=journal_parameters.licence,
        copyright_text=journal_parameters.copyright,
        user_can_select_access_mode=False,
    )
    RevisionStorage.objects.create(
        article=article,
        revision_flow_type=RevisionStorage.RevisionFlowType.FULL,
        data={
            "correspondence_author": article.correspondence_author.pk,
            "affiliation_pk": None if affiliation_changed else article.submission_data.affiliation_id,
            "access_mode": other.pk,
            "special_request": "",
        },
    )

    with patch("plugins.wjs_submission.access_mode.import_string", return_value=lambda user, article: calculated):
        configuration = get_access_mode_configuration(user, article)

    if affiliation_changed:
        assert configuration == calculated
    else:
        assert configuration.access_mode == other
        assert configuration.license == licence
        assert configuration.copyright_text == "original rights"
    form = RevisionStep7Form(
        data={"special_request": "", "access_mode": configuration.access_mode.pk},
        journal=journal,
        instance=article,
        step=7,
        configuration=configuration,
        revision_full=True,
        initial={},
    )
    assert form.is_valid(), form.errors
    form.save()
    article.revisionstorage.refresh_from_db()
    assert article.revisionstorage.data["access_mode"] == (oa.pk if affiliation_changed else other.pk)


@pytest.mark.django_db
def test_preserve_keywords_metadata_form5(
    journal: Journal, install_plugins: Callable, user: Account, article: Article, fake_request, hierarchical_keywords
):
    """
    Form for step 5 does not clear keywords set in step 3.

    :param journal: Journal instance used in the test.
    :param install_plugins: Callable function for installing plugins.
    :param user: Account instance representing the user.
    :param article: Article instance being tested.
    :param fake_request: Mock request object for testing.
    :param hierarchical_keywords: Hierarchical keywords for testing.
    """
    keywords = {"kw1": "group1", "kw2": "group2"}
    keyword_values = {}

    for name, group_name in keywords.items():
        group = KeywordGroup.objects.get_or_create(name=group_name)[0] if group_name else None
        keyword_values[name] = Keyword.objects.create(word=name, group=group)
        journal.keywords.add(keyword_values[name])

    data = QueryDict(f"keyword_{keyword_values['kw1'].pk}_weight=50&keyword_{keyword_values['kw2'].pk}_weight=50")
    form_3 = SubmissionStep3Form(data={"state": "state"}, form_data=data, instance=article, step=3)
    assert form_3.is_valid()
    form_3.save()
    article.refresh_from_db()
    assert article.keywords.count() == 2
    form_5 = SubmissionStep5Form(
        data={
            "title": article.title,
            "language": article.language,
            "section": article.section,
            "license": article.license,
        },
        instance=article,
        step=5,
    )
    assert form_5.is_valid()
    form_5.save()
    article.refresh_from_db()
    assert article.keywords.count() == 2


@pytest.mark.django_db
def test_step5_form_correction_preserves_license_and_rights(
    journal: Journal,
    install_plugins: Callable,
    article: Article,
    fake_request: HttpRequest,
):
    """
    License and rights set up for a correction are not changed by step 5, not even by the journal defaults.
    """
    default_licence = Licence.objects.create(short_name="default", name="Default", journal=journal)
    journal.submissionconfiguration.license = False
    journal.submissionconfiguration.default_license = default_licence
    journal.submissionconfiguration.save()
    licence = Licence.objects.create(short_name="original", name="Original", journal=journal)
    article.license = licence
    article.rights = "original rights"
    article.save()
    form = SubmissionStep5Form(
        data={
            "title": article.title,
            "abstract": article.abstract,
            "language": article.language,
            "license": "",
            "rights": "",
        },
        journal=journal,
        instance=article,
        step=5,
        is_correction=True,
    )
    assert "license" not in form.fields
    assert "rights" not in form.fields
    assert form.is_valid(), form.errors
    form.save(request=fake_request)
    article.refresh_from_db()
    assert article.license == licence
    assert article.rights == "original rights"


@pytest.mark.django_db
def test_projected_issue_is_assigned_at_the_end_of_the_submission(
    journal: Journal,
    install_plugins: Callable,
    author: Account,
    article: Article,
    fake_request: HttpRequest,
):
    """
    The issue selected in step 2 becomes the article primary issue and is linked to the article.

    The link to Issue.articles is created only at the end of step 8, because it triggers janeway's
    "issue_articles_change" signal, which creates an ArticleOrdering whose section cannot be null, and the
    article section is chosen in step 5.

    :param journal: The journal of the submission.
    :param install_plugins: Fixture setting up the plugins for the journal.
    :param author: The author of the article, i.e. the user doing the submission.
    :param article: The article being submitted.
    :param fake_request: A request suitable for the submission views / forms.
    """
    fake_request.user = author
    issue = Issue.objects.create(
        journal=journal,
        issue_type=IssueType.objects.get(journal=journal, code="collection"),
        issue_title="Special issue",
        date_open=now() - timedelta(days=1),
        date_close=now() + timedelta(days=1),
    )

    form_2 = SubmissionStep2Form(
        data={"projected_issue": issue.pk},
        instance=article,
        journal=journal,
        user=author,
        request=fake_request,
        step=2,
    )
    assert form_2.is_valid()
    form_2.save()

    article.refresh_from_db()
    assert article.projected_issue == issue
    assert article.primary_issue == issue
    # The article is linked to the issue only at the end of the submission
    assert not article.issues.exists()
    assert not ArticleOrdering.objects.filter(article=article).exists()

    form_8 = SubmissionStep8Form(data={}, instance=article, request=fake_request, revision=False, step=8)
    assert form_8.is_valid()
    # The events raised at the end of the submission are subscribed to by other plugins (wjs_review), which are not
    # necessarily installed: they are irrelevant here and would drag in their own setup requirements.
    with patch.object(event_logic.Events, "raise_event"):
        form_8.save()

    article.refresh_from_db()
    assert article.primary_issue == issue
    assert list(article.issues.all()) == [issue]
    assert ArticleOrdering.objects.filter(article=article, issue=issue, section=article.section).exists()


@pytest.mark.django_db
def test_keyword_handling_rollback(client, article):
    """
    A rejected keyword selection leaves the article's existing keywords untouched.

    Saving the form clears the existing keyword relations before the new weights are validated, so the whole save
    must be rolled back when validation fails.
    """
    keyword = Keyword.objects.create(word="keyword1", journal=article.journal)
    KeywordArticle.objects.create(article=article, keyword=keyword, weight=50, order=1)

    client.force_login(article.owner)
    url = reverse("wjs_submission_3", kwargs={"article_id": article.pk})

    response = client.post(url, {f"keyword_{keyword.pk}_weight": ["abc"]})

    assert response.status_code == 200
    assert not response.context_data["form"].is_valid()
    weights = {ka.keyword_id: ka.weight for ka in KeywordArticle.objects.filter(article=article)}
    assert weights == {keyword.pk: 50}


@pytest.mark.django_db
def test_add_collaboration_form_sets_creator(article: Article, user: Account):
    """Saving AddCollaborationForm records the current user as the collaboration's creator."""
    form = AddCollaborationForm(
        data={"name": "Test Collaboration", "institutional_email": "", "collaboration_relation": "by"},
        is_revision=False,
        article=article,
        collaboration_relation="by",
        user=user,
    )

    assert form.is_valid(), form.errors
    collaboration = form.save()

    assert collaboration.creator == user
