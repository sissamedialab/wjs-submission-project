from core.models import Account, ControlledAffiliation
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from repository.models import Author
from submission.models import LANGUAGE_CHOICES, Article, FrozenAuthor, Section
from utils.setting_handler import get_setting

from ..access_mode import get_access_mode_configuration
from ..data import RevisionValidationData
from ..mixins import AuthorFilteringView, StepCheckView
from ..models import (
    AccessModeJournal,
    ArticleCollaboration,
    RevisionArticleAuthorOrder,
    RevisionArticleCollaboration,
    RevisionStorage,
)
from ..step6.views import get_conversion_status, get_files
from ..step7.views import get_article_fundings
from ..workflow import (
    is_revision,
    is_revision_confirm,
    is_revision_full,
    is_revision_metadata,
    step_check_access_funding,
    step_check_select_issue,
)
from .forms import RevisionForm, SubmissionStep8Form


def get_article_authors(article) -> list[Author]:
    if is_revision_full(article) or is_revision_metadata(article):
        return [
            author.author for author in RevisionArticleAuthorOrder.objects.filter(revision_storage__article=article)
        ]
    return [author.author for author in FrozenAuthor.objects.filter(article=article)]


def get_article_collaborations(article) -> list[RevisionArticleCollaboration] | list[ArticleCollaboration]:
    if is_revision_full(article) or is_revision_metadata(article):
        return list(RevisionArticleCollaboration.objects.filter(revision_storage__article=article))
    return list(ArticleCollaboration.objects.filter(article=article))


class SubmissionStep8View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 8
    template_name = "wjs_submission/step8/article_form.html"

    def get_success_url(self):
        """
        Redirect to the status page through wjs_submission_0.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_0", kwargs={"article_id": self.object.pk})

    def get_form_class(self):
        """Return the revision-form."""
        if is_revision(self.object):
            return RevisionForm
        return SubmissionStep8Form

    def _step7_skipped(self) -> bool:
        """
        Determine whether step 7 is skipped based on access funding check.

        :return: True if step 7 is skipped, False otherwise
        :rtype: bool
        """
        return not step_check_access_funding(self.object.journal, self.object, self.request.user)

    def _process_step7(self):
        """
        Assign the access mode configuration if the step7 is skipped.

        :raises Exception: If exceptions occur during the process of fetching or saving the configuration
        """
        configuration = get_access_mode_configuration(self.request.user, self.object)
        editable_revision = is_revision_full(self.object) or is_revision_metadata(self.object)
        if not editable_revision and self._step7_skipped() and configuration.access_mode:
            self.object.submission_data.access_mode = configuration.access_mode
            self.object.submission_data.save()
        if editable_revision and self._step7_skipped() and configuration.access_mode:
            revision_storage = RevisionStorage.objects.get(article=self.object)
            revision_storage.data["access_mode"] = configuration.access_mode.pk
            revision_storage.save()

    def get_form_kwargs(self):
        """
        Inject necessary data into the form.

        Process step 7 if skipped due to single access mode and funding is not enabled.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["step"] = self.step
        self._process_step7()
        return kwargs

    def _validate_revision_data(self, article: Article) -> RevisionValidationData:
        """
        Validate the revision data of an article to ensure completeness.

        :param article: The article object containing revision data
        :type article: Article
        :return: Validation results for different aspects of the revision data.
        :rtype: RevisionValidationData
        :raises KeyError: If expected keys are missing in the revision data
        """
        if is_revision(article):
            submission_requirements = bool(article.revisionstorage.data["submission_requirements"])
            if article.journal.submissionconfiguration.comments_to_the_editor:
                cover_letter = bool(article.revisionstorage.data["comments_editor"]) or bool(
                    article.revisionstorage.data["cover_letter_file"]
                )
            else:
                cover_letter = True
            if is_revision_full(self.object):
                revision_files = bool(article.revisionstorage.data["source_files"]) and bool(
                    article.revisionstorage.data["manuscript_files"]
                )
            else:
                revision_files = True
        else:
            submission_requirements = bool(article.submission_requirements)
            cover_letter = bool(article.comments_editor) or bool(article.submission_data.cover_letter_file)
            revision_files = False
        return {
            "valid": submission_requirements and cover_letter and revision_files,
            "submission_requirements": submission_requirements,
            "cover_letter": cover_letter,
            "revision_files": revision_files,
        }

    def get_context_data(self, **kwargs):
        """
        Inject necessary data into the context.

        :return: Context data.
        """
        context = super().get_context_data(**kwargs)
        if arxiv_identifier := context["article"].identifiers.filter(id_type="arxiv").first():
            context["arxiv_id"] = arxiv_identifier.identifier
        context["show_issue"] = step_check_select_issue(self.object.journal, user=self.request.user)
        context["is_revision"] = is_revision(self.object)
        context["is_revision_metadata"] = is_revision_metadata(self.object)
        context["is_revision_full"] = is_revision_full(self.object)
        context["is_revision_confirm"] = is_revision_confirm(self.object)
        context["articles_fundings"] = get_article_fundings(self.object)
        context["article_authors"] = get_article_authors(self.object)
        context["article_collaborations"] = get_article_collaborations(self.object)
        enable_cas = get_setting("wjs_submission", "enable_cas", self.object.journal).processed_value
        enable_das = get_setting("wjs_submission", "enable_das", self.object.journal).processed_value
        context["files_data"] = {}
        if context["is_revision_full"]:
            context["article_data"] = self.object.revisionstorage.data
            if enable_cas:
                context["files_data"].update(
                    {
                        "cas": self.object.revisionstorage.data["cas"],
                        "cas_display": self.object.submission_data.CasDeclaration.as_dict()[
                            self.object.revisionstorage.data["cas"]
                        ],
                        "cas_url": self.object.revisionstorage.data["cas_url"],
                        "cas_show_url": self.object.revisionstorage.data["cas"]
                        == self.object.submission_data.CasDeclaration.URL.value,
                    }
                )
            if enable_das:
                context["files_data"].update(
                    {
                        "das": self.object.revisionstorage.data["das"],
                        "das_display": self.object.submission_data.CasDeclaration.as_dict()[
                            self.object.revisionstorage.data["das"]
                        ],
                        "das_url": self.object.revisionstorage.data["das_url"],
                        "das_show_url": self.object.revisionstorage.data["das"]
                        == self.object.submission_data.DasDeclaration.URL.value,
                    }
                )
            if context["article_data"].get("language"):
                context["article_data"]["language"] = dict(LANGUAGE_CHOICES)[context["article_data"]["language"]]
            if context["article_data"].get("section"):
                context["article_data"]["section"] = Section.objects.get(pk=context["article_data"]["section"])
            context["access_mode"] = AccessModeJournal.objects.get(
                journal=self.object.journal, access_mode_id=context["article_data"].get("access_mode", None)
            )
            context["correspondence_author"] = Account.objects.get(pk=context["article_data"]["correspondence_author"])
            if context["article_data"].get("affiliation_pk", None):
                context["affiliation"] = ControlledAffiliation.objects.get(
                    pk=context["article_data"]["affiliation_pk"]
                )
            context["validate_revision_data"] = self._validate_revision_data(self.object)
            context["authors_contributions"] = self.object.revisionstorage.data.get("authors_contributions")
        else:
            context["article_data"] = self.object
            if enable_cas:
                context["files_data"].update(
                    {
                        "cas": self.object.submission_data.cas,
                        "cas_display": self.object.submission_data.get_cas_display(),
                        "cas_url": self.object.submission_data.cas_url,
                        "cas_show_url": self.object.submission_data.cas
                        == self.object.submission_data.CasDeclaration.URL.value,
                    }
                )
            if enable_das:
                context["files_data"].update(
                    {
                        "das": self.object.submission_data.das,
                        "das_display": self.object.submission_data.get_das_display(),
                        "das_url": self.object.submission_data.das_url,
                        "das_show_url": self.object.submission_data.das
                        == self.object.submission_data.DasDeclaration.URL.value,
                    }
                )
            context["access_mode"] = AccessModeJournal.objects.get(
                journal=self.object.journal, access_mode_id=self.object.submission_data.access_mode.pk
            )
            context["correspondence_author"] = self.object.correspondence_author
            context["affiliation"] = self.object.submission_data.affiliation
            if context["is_revision"]:
                if title := self.object.revisionstorage.data.get("title"):
                    context["article_data"].title = title
                if abstract := self.object.revisionstorage.data.get("abstract"):
                    context["article_data"].abstract = abstract
                if language := self.object.revisionstorage.data.get("language"):
                    context["article_data"].language = dict(LANGUAGE_CHOICES)[language]
                if section := self.object.revisionstorage.data.get("section"):
                    context["article_data"].section = Section.objects.get(pk=section)
                context["article_data"].special_request = self.object.revisionstorage.data.get("special_request", "")
                context["article_data"].comments_editor = self.object.revisionstorage.data.get("comments_editor", "")
                context["article_data"].cover_letter_file = self.object.revisionstorage.data.get(
                    "cover_letter_file", ""
                )
                context["article_data"].competing_interests = self.object.revisionstorage.data.get(
                    "competing_interests", ""
                )
            else:
                context["article_data"].language = self.object.get_language_display()
                context["article_data"].special_request = self.object.submission_data.special_request
                context["article_data"].cover_letter_file = self.object.submission_data.cover_letter_file
            context["validate_revision_data"] = self._validate_revision_data(self.object)

        # Include files (manuscript_files, data_figure_files, etc.)
        context.update(get_files(article=self.object))

        # Include info about the conversion status
        context.update(get_conversion_status(article=self.object, view=self))

        return context
