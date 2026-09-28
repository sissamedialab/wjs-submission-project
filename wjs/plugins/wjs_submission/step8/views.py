from core.models import Account, ControlledAffiliation
from core.models import File as CoreFile
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView
from repository.models import Author
from submission.models import LANGUAGE_CHOICES, Article, FrozenAuthor, Section
from utils.setting_handler import get_setting

from ..data import RevisionValidationData
from ..mixins import AuthorFilteringView, StepCheckView
from ..models import (
    AccessModeJournal,
    ArticleCollaboration,
    RevisionArticleAuthorOrder,
    RevisionArticleCollaboration,
)
from ..step6.views import get_conversion_status, get_files
from ..step7.views import get_article_fundings
from ..workflow import (
    is_correction,
    is_revision,
    is_revision_confirm,
    is_revision_full,
    is_revision_metadata,
    step_check_select_issue,
)
from .forms import SubmissionStep8Form


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
    form_class = SubmissionStep8Form

    def get_success_url(self):
        """
        Redirect to the status page through wjs_submission_0.

        :return: Next step URL.
        """
        return reverse_lazy("wjs_submission_0", kwargs={"article_id": self.object.pk})

    @property
    def message_text(self):
        """
        Get a textual message indicating the submission status of an article.

        This property returns a formatted message string that includes the title of the
        article for which the action occurred. The message format differs depending on
        whether the article is a revision or a new submission.

        :return: A formatted message string describing the article submission status.
        :rtype: str
        """
        if is_correction(self.object):
            # Determine if it's an erratum or addendum from the section name.
            section_name = self.object.section.name if self.object.section else "Correction"
            kind = section_name.lower()
            return _('{kind} for article "{title}" submitted').format(
                kind=kind.capitalize(),
                title=self.object.title,
            )
        if is_revision(self.object):
            return _('Revision for article "{title}" submitted').format(
                title=self.object.title,
            )
        return _('Article "{title}" submitted').format(
            title=self.object.title,
        )

    @property
    def message_error_text(self):
        """
        Get a textual message indicating errors in the submission status of an article.

        This property returns a formatted message string that includes the title of the
        article for which the action occurred. The message format differs depending on
        whether the article is a revision or a new submission.

        :return: A formatted message string describing the article submission status.
        :rtype: str
        """
        if is_revision(self.object):
            return _('Error during the revision for article "{title}"').format(
                title=self.object.title,
            )
        return _('Error during the submission of "{title}"').format(
            title=self.object.title,
        )

    def form_valid(self, form):
        """
        Process the submitted form and sends a success message upon successful validation.

        The form_valid method is triggered upon successful validation of the form and
        adds a success message to the request, indicating that submission of the
        article was successful. It then returns the result of the superclass
        implementation of the `form_valid` method.

        :param form: The submitted form to be validated.
        :return: HTTP response object returned after processing the form.
        """
        try:
            response = super().form_valid(form)
            messages.add_message(
                self.request,
                messages.SUCCESS,
                self.message_text,
            )
        except ValidationError as e:
            form.add_error(None, e)
            response = super().form_invalid(form)
            messages.add_message(
                self.request,
                messages.ERROR,
                self.message_error_text,
            )
        return response

    def get_form_kwargs(self):
        """
        Inject necessary data into the form.

        Process step 7 if skipped due to single access mode and funding is not enabled.

        :return: Form kwargs.
        """
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["step"] = self.step
        kwargs["revision"] = is_revision(self.object)
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
        if context["is_revision"]:
            context["article_data"] = self.object.revisionstorage.data
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
                            "das_display": self.object.submission_data.DasDeclaration.as_dict()[
                                self.object.revisionstorage.data["das"]
                            ],
                            "das_url": self.object.revisionstorage.data["das_url"],
                            "das_show_url": self.object.revisionstorage.data["das"]
                            == self.object.submission_data.DasDeclaration.URL.value,
                        }
                    )
            else:
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
            if context["is_revision_full"] or context["is_revision_metadata"]:
                if context["article_data"].get("language"):
                    context["article_data"]["language"] = dict(LANGUAGE_CHOICES)[context["article_data"]["language"]]
                if context["article_data"].get("section"):
                    context["article_data"]["section"] = Section.objects.get(pk=context["article_data"]["section"])
                context["access_mode"] = AccessModeJournal.objects.get(
                    journal=self.object.journal, access_mode_id=context["article_data"].get("access_mode", None)
                )
                context["correspondence_author"] = Account.objects.get(
                    pk=context["article_data"]["correspondence_author"]
                )
                if context["article_data"].get("affiliation_pk", None):
                    context["affiliation"] = ControlledAffiliation.objects.get(
                        pk=context["article_data"]["affiliation_pk"]
                    )
                context["authors_contributions"] = self.object.revisionstorage.data.get("authors_contributions")
                context["article_data"]["special_request"] = self.object.revisionstorage.data.get(
                    "special_request", ""
                )
                context["article_data"]["comments_editor"] = self.object.revisionstorage.data.get(
                    "comments_editor", ""
                )
            else:
                context["article_data"]["title"] = self.object.title
                context["article_data"]["abstract"] = self.object.abstract
                context["article_data"]["language"] = self.object.get_language_display()
                context["article_data"]["section"] = self.object.section
                context["access_mode"] = AccessModeJournal.objects.get(
                    journal=self.object.journal, access_mode_id=self.object.submission_data.access_mode.pk
                )
                context["correspondence_author"] = self.object.correspondence_author
                context["affiliation"] = self.object.submission_data.affiliation
                context["article_data"]["special_request"] = self.object.submission_data.special_request
            if context["is_revision_full"] or context["is_revision_confirm"]:
                cover_file = self.object.revisionstorage.data.get("cover_letter_file", "")
                if cover_file:
                    context["article_data"]["cover_letter_file"] = CoreFile.objects.get(pk=cover_file)
            context["validate_revision_data"] = self._validate_revision_data(self.object)
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
            context["article_data"].language = self.object.get_language_display()
            context["article_data"].special_request = self.object.submission_data.special_request
            context["article_data"].cover_letter_file = self.object.submission_data.cover_letter_file
            context["validate_revision_data"] = self._validate_revision_data(self.object)

        # Include files (manuscript_files, data_figure_files, etc.)
        context.update(get_files(article=self.object))

        # Include info about the conversion status
        context.update(get_conversion_status(article=self.object, view=self))

        return context
