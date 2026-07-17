"""Tests for ArticleSubmission admin form and access mode / license / copyright handling."""

import pytest
from django.contrib import admin as django_admin
from django.test import RequestFactory
from plugins.wjs_submission import settings as wjs_settings
from plugins.wjs_submission.advanced_admin.advanced_admin import ArticleSubmissionAdmin
from plugins.wjs_submission.advanced_admin.forms import ArticleSubmissionAdminForm
from plugins.wjs_submission.models import AccessMode, AccessModeJournal, ArticleSubmission
from submission.models import Licence


@pytest.fixture
def access_mode_journal(journal):
    """Create an AccessModeJournal linking an access mode to the journal with a specific licence and copyright."""
    access_mode = AccessMode.objects.create(name="Test OA", code="test-oa", user_selectable=True)
    licence = Licence.objects.create(
        name="cc-by-4.0-test",
        short_name="CC BY 4.0 test",
        url="http://example.com/cc-by",
        journal=journal,
    )
    return AccessModeJournal.objects.create(
        access_mode=access_mode,
        journal=journal,
        licence=licence,
        copyright="© Test copyright",
    )


@pytest.fixture
def article_submission(article, access_mode_journal):
    """
    Create an ArticleSubmission linked to the article with an access mode set.

    If ArticleSubmission already exist we update it instead of creating a new one.
    """
    submission, _ = ArticleSubmission.objects.get_or_create(article=article)
    submission.access_mode = access_mode_journal.access_mode
    submission.save()
    article.refresh_from_db()
    return submission


@pytest.mark.django_db
class TestArticleSubmissionSave:
    """Test that ArticleSubmission.save() correctly handles license and rights overrides."""

    def test_save_syncs_license_and_rights_from_access_mode(self, article_submission, access_mode_journal):  # noqa: PLR6301
        """When no override flags are set, saving syncs license and rights from AccessModeJournal."""
        article = article_submission.article
        article.refresh_from_db()
        assert article.license == access_mode_journal.licence
        assert article.rights == access_mode_journal.copyright

    def test_save_with_license_override_preserves_article_license(self, article_submission, access_mode_journal):  # noqa: PLR6301
        """When license_override is set, saving does not overwrite the article's license."""
        article = article_submission.article
        custom_licence = Licence.objects.create(
            name="custom-licence",
            short_name="Custom Licence",
            url="http://example.com/custom",
            journal=article.journal,
        )
        article.license = custom_licence
        article.save()

        article_submission.license_override = True
        article_submission.save()

        article.refresh_from_db()
        assert article.license == custom_licence
        assert article.rights == access_mode_journal.copyright

    def test_save_with_rights_override_preserves_article_rights(self, article_submission, access_mode_journal):  # noqa: PLR6301
        """When rights_override is set, saving does not overwrite the article's rights."""
        article = article_submission.article
        custom_rights = "© Custom copyright"
        article.rights = custom_rights
        article.save()

        article_submission.rights_override = True
        article_submission.save()

        article.refresh_from_db()
        assert article.license == access_mode_journal.licence
        assert article.rights == custom_rights

    def test_save_with_both_overrides_preserves_both(self, article_submission, access_mode_journal):  # noqa: PLR6301
        """When both override flags are set, saving preserves both license and rights."""
        article = article_submission.article
        custom_licence = Licence.objects.create(
            name="custom-licence-both",
            short_name="CustomLicBoth",
            url="http://example.com/custom-both",
            journal=article.journal,
        )
        custom_rights = "© Custom copyright both"
        article.license = custom_licence
        article.rights = custom_rights
        article.save()

        article_submission.license_override = True
        article_submission.rights_override = True
        article_submission.save()

        article.refresh_from_db()
        assert article.license == custom_licence
        assert article.rights == custom_rights


@pytest.mark.django_db
class TestArticleSubmissionAdminForm:
    """Test the custom admin form that handles cross-model fields."""

    def test_form_initial_values_from_article(self, article_submission, access_mode_journal):  # noqa: PLR6301
        """The form should show the article's current license and rights as initial values."""
        article = article_submission.article
        article.license = access_mode_journal.licence
        article.rights = "© Initial rights"
        article.save()

        form = ArticleSubmissionAdminForm(instance=article_submission)
        assert form.fields["article_license"].initial == article.license
        assert form.fields["article_rights"].initial == "© Initial rights"

    def test_form_license_queryset_filtered_by_journal(self, article_submission):  # noqa: PLR6301
        """The license queryset should be filtered by the article's journal."""
        form = ArticleSubmissionAdminForm(instance=article_submission)
        journal = article_submission.article.journal
        assert not form.fields["article_license"].queryset.exclude(journal=journal).exists()

    def test_form_fields_disabled_when_override_not_set(self, article_submission):  # noqa: PLR6301
        """License and copyright fields should be disabled when the override flag is not set."""
        article_submission.license_override = False
        article_submission.rights_override = False
        article_submission.save()

        form = ArticleSubmissionAdminForm(instance=article_submission)
        assert form.fields["article_license"].disabled is True
        assert form.fields["article_rights"].disabled is True

    def test_form_fields_enabled_when_override_set(self, article_submission):  # noqa: PLR6301
        """License and copyright fields should be editable when the override flag is set."""
        article_submission.license_override = True
        article_submission.rights_override = True
        article_submission.save()

        form = ArticleSubmissionAdminForm(instance=article_submission)
        assert form.fields["article_license"].disabled is False
        assert form.fields["article_rights"].disabled is False

    def test_form_save_with_override_updates_article(self, article_submission, access_mode_journal):  # noqa: PLR6301
        """Saving the form with override flags should update the article's license and rights."""
        article = article_submission.article
        new_licence = Licence.objects.create(
            name="new-licence",
            short_name="New Licence",
            url="http://example.com/new",
            journal=article.journal,
        )
        form = ArticleSubmissionAdminForm(
            data={
                "cover_letter_file": "",
                "access_mode": access_mode_journal.access_mode.pk,
                "article_license": new_licence.pk,
                "article_rights": "© New rights",
                "license_override": True,
                "rights_override": True,
                "special_request": "",
            },
            instance=article_submission,
        )
        assert form.is_valid(), form.errors
        form.save()

        article.refresh_from_db()
        assert article.license == new_licence
        assert article.rights == "© New rights"

    def test_form_save_without_override_syncs_from_config(self, article_submission, access_mode_journal):  # noqa: PLR6301
        """When override flags are not set, saving the form should sync license and rights from AccessModeJournal."""
        article = article_submission.article
        # Set custom values on the article that differ from config
        custom_licence = Licence.objects.create(
            name="will-be-overwritten",
            short_name="WillOverwrite",
            url="http://example.com/overwritten",
            journal=article.journal,
        )
        article.license = custom_licence
        article.rights = "© Will be overwritten"
        article.save()

        form = ArticleSubmissionAdminForm(
            data={
                "cover_letter_file": "",
                "access_mode": access_mode_journal.access_mode.pk,
                "article_license": custom_licence.pk,
                "article_rights": "© Will be overwritten",
                "license_override": False,
                "rights_override": False,
                "special_request": "",
            },
            instance=article_submission,
        )
        assert form.is_valid(), form.errors
        form.save()

        article.refresh_from_db()
        # Without override, model save() should have synced from config
        assert article.license == access_mode_journal.licence
        assert article.rights == access_mode_journal.copyright

    def test_form_unchecking_override_reverts_to_config(self, article_submission, access_mode_journal):  # noqa: PLR6301
        """Unchecking an override flag should cause the next save to sync from config again."""
        article = article_submission.article
        custom_licence = Licence.objects.create(
            name="temp-custom",
            short_name="Temp Custom",
            url="http://example.com/temp-custom",
            journal=article.journal,
        )
        # First save with override to set a custom license
        article_submission.license_override = True
        article_submission.save()
        article.license = custom_licence
        article.save()

        # Now uncheck override and save via form
        form = ArticleSubmissionAdminForm(
            data={
                "cover_letter_file": "",
                "access_mode": access_mode_journal.access_mode.pk,
                "article_license": custom_licence.pk,
                "article_rights": article.rights,
                "license_override": False,
                "rights_override": False,
                "special_request": "",
            },
            instance=article_submission,
        )
        assert form.is_valid(), form.errors
        form.save()

        article.refresh_from_db()
        # Without override, license should be re-synced from config
        assert article.license == access_mode_journal.licence


@pytest.mark.django_db
class TestArticleSubmissionAdminReadOnly:
    """Test that access_mode is read-only for non-IoP journals and editable for IoP journals."""

    def test_access_mode_readonly_for_non_iop_journal(self, article_submission):  # noqa: PLR6301
        """For non-IoP journals, access_mode should be in readonly_fields."""
        rf = RequestFactory()
        request = rf.get("/")
        admin_instance = ArticleSubmissionAdmin(
            ArticleSubmission,
            django_admin.site,
        )
        readonly_fields = admin_instance.get_readonly_fields(request, obj=article_submission)
        assert "access_mode" in readonly_fields

    def test_access_mode_editable_for_iop_journal(self, article_submission, monkeypatch):  # noqa: PLR6301
        """For IoP journals, access_mode should not be in readonly_fields."""
        monkeypatch.setattr(wjs_settings, "IOP_JOURNALS", [article_submission.article.journal.code])

        rf = RequestFactory()
        request = rf.get("/")
        admin_instance = ArticleSubmissionAdmin(
            ArticleSubmission,
            django_admin.site,
        )
        readonly_fields = admin_instance.get_readonly_fields(request, obj=article_submission)
        assert "access_mode" not in readonly_fields
