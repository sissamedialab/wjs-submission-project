from django.contrib import admin

from .advanced_admin import advanced_admin  # noqa: F401
from .models import (
    AccessMode,
    AccessModeJournal,
    ArticleCollaboration,
    ArticleSubmission,
    Collaboration,
    RevisionStorage,
    WhitelistedCorrespondenceAuthors,
)


@admin.register(ArticleSubmission)
class ArticleSubmissionAdmin(admin.ModelAdmin):
    search_fields = ("article_id",)


@admin.register(Collaboration)
class CollaborationAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "institutional_email", "public_listing", "creator", "linked_account")
    list_filter = ("public_listing", "cluster", "author_list_mode", "collaboration_list_mode")
    search_fields = ("name", "short_name", "institutional_email", "address", "notes", "logo_name")
    raw_id_fields = ("logo", "creator", "linked_account")
    ordering = ("name",)


@admin.register(ArticleCollaboration)
class ArticleCollaborationAdmin(admin.ModelAdmin):
    list_display = ("article", "collaboration", "relation", "order")
    list_filter = ("relation",)
    search_fields = (
        "article__title",
        "collaboration__name",
    )
    raw_id_fields = ("article", "collaboration")
    ordering = ("article", "order")


class AccessModeJournalInlineAdmin(admin.TabularInline):
    model = AccessModeJournal
    extra = 0


@admin.register(AccessMode)
class AccessModeAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")
    inlines = [AccessModeJournalInlineAdmin]


@admin.register(WhitelistedCorrespondenceAuthors)
class WhitelistedCorrespondenceAuthorsAdmin(admin.ModelAdmin):
    list_display = ("user", "validity_start_date", "validity_stop_date")
    search_fields = ("user__email",)
    list_filter = ["journal"]


@admin.register(RevisionStorage)
class RevisionStorageAdmin(admin.ModelAdmin):
    list_display = ("article_id", "revision_flow_type", "revision_step")
    search_fields = ("article_id",)
    list_filter = ["article__journal"]
