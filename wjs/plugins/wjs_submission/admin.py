from django.contrib import admin

from .models import ArticleSubmission


@admin.register(ArticleSubmission)
class ArticleSubmissionAdmin(admin.ModelAdmin):
    search_fields = ("article_id",)
