from django.contrib import admin

from .models import ArticleCollaboration, ArticleSubmission, Collaboration


@admin.register(ArticleSubmission)
class ArticleSubmissionAdmin(admin.ModelAdmin):
    search_fields = ("article_id",)


@admin.register(Collaboration)
class CollaborationAdmin(admin.ModelAdmin):
    list_display = ("name", "institutional_email", "public_listing", "creator", "linked_account")
    list_filter = ("public_listing",)
    search_fields = ("name", "institutional_email", "address", "notes")
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
