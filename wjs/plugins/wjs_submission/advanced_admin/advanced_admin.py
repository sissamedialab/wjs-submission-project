from django.contrib import admin, messages
from django.shortcuts import redirect, render, reverse
from django.urls import path
from wjs.advanced_admin.admin import advanced_admin_site

from ..models import ArticleCollaboration, Collaboration
from .forms import CollaborationMergeForm


class ArticleCollaborationInline(admin.TabularInline):
    model = ArticleCollaboration
    extra = 1
    raw_id_fields = ("article",)
    autocomplete_fields = ("article",)
    fields = ("article", "relation", "order")


@admin.register(Collaboration, site=advanced_admin_site)
class CollaborationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "institutional_email",
        "public_listing",
        "creator",
        "linked_account",
        "article_list",
    )
    list_filter = ("public_listing",)
    search_fields = ("name", "institutional_email", "address", "notes", "articles__title")
    raw_id_fields = ("logo", "creator", "linked_account")
    ordering = ("name",)
    change_list_template = "admin/wjs_submission/collaboration/change_list.html"
    inlines = [ArticleCollaborationInline]

    def article_list(self, obj):  # noqa: PLR6301
        """Return a comma-separated list of the first five article titles for this collaboration."""
        return ", ".join(obj.articles.values_list("article__title", flat=True)[:5])

    article_list.short_description = "Articles"

    def get_urls(self):
        """
        Extend the default admin URL set with a custom route for merging collaborations.

        Add the "merge/" endpoint, mapped to `merge_view`, under this admin site.
        """
        urls = super().get_urls()
        custom_urls = [
            path("merge/", self.admin_site.admin_view(self.merge_view), name="wjs_submission_collaboration_merge"),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        """
        Inject the merge view URL into the changelist context.

        Ensure the template can access the merge action link via `merge_url`.
        """
        merge_url = reverse("advanced_admin:wjs_submission_collaboration_merge")
        extra_context = extra_context or {}
        extra_context["merge_url"] = merge_url
        return super().changelist_view(request, extra_context=extra_context)

    def merge_view(self, request):
        """
        Handle the merge operation between two Collaboration objects.

        If the submitted form is valid, reassign all Articles linked to the merged Collaboration
        to the kept one, delete the merged Collaboration, and display a success message.
        Otherwise, render the merge form template.
        """
        form = CollaborationMergeForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            kept = form.cleaned_data["kept"]
            merged = form.cleaned_data["merged"]

            for ac in merged.articles.all():
                if ArticleCollaboration.objects.filter(article=ac.article, collaboration=kept).exists():
                    continue
                ArticleCollaboration.objects.create(
                    article=ac.article,
                    collaboration=kept,
                    relation=ac.relation,
                    order=Collaboration.next_collaboration_sort(ac.article),
                )

            merged.delete()
            messages.success(request, f"Merged '{merged}' into '{kept}'.")
            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Merge two collaborations",
        }
        return render(request, "admin/wjs_submission/collaboration/merge_collaborations.html", context)
