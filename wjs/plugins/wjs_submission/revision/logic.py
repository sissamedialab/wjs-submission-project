import dataclasses

from django.db.transaction import atomic
from submission.models import STAGE_UNDER_REVISION, Article, ArticleAuthorOrder

from ..models import (
    ArticleCollaboration,
    CollaborationRelation,
    RevisionArticleAuthorOrder,
    RevisionArticleCollaboration,
    RevisionStorage,
)


@dataclasses.dataclass
class BaseSetupRevisionStorage:
    article_id: int
    revision_flow_type: RevisionStorage.RevisionFlowType = None
    revision_storage: RevisionStorage = None
    created: bool = False

    def _check_conditions(self):
        article = Article.objects.get(pk=self.article_id)
        return article.stage == STAGE_UNDER_REVISION

    def _ensure_storage(self):
        self.revision_storage, self.created = RevisionStorage.objects.get_or_create(article_id=self.article_id)
        self.revision_storage.revision_flow_type = self.revision_flow_type

    def _populate_additional_models(self):
        pass

    def _populate_storage(self):
        raise NotImplementedError

    def run(self):
        """Run the initialization of the RevisionStorage object according to the initialized revision flow."""
        with atomic():
            if not self._check_conditions():
                raise ValueError(f"Conditions for starting revision {self.revision_flow_type} not met.")
            self._ensure_storage()
            self._populate_storage()
            self._populate_additional_models()


@dataclasses.dataclass
class SetupRevisionStorageConfirm(BaseSetupRevisionStorage):
    revision_flow_type: RevisionStorage.RevisionFlowType = RevisionStorage.RevisionFlowType.CONFIRM

    def _populate_storage(self):
        self.revision_storage.data["submission_requirements"] = False
        self.revision_storage.data["cover_letter_file"] = None
        self.revision_storage.data["comments_editor"] = ""
        self.revision_storage.save()


@dataclasses.dataclass
class SetupRevisionStorageMetadata(BaseSetupRevisionStorage):
    revision_flow_type: RevisionStorage.RevisionFlowType = RevisionStorage.RevisionFlowType.METADATA

    def _populate_storage(self):
        self.revision_storage.data["submission_requirements"] = False
        self.revision_storage.data["cover_letter_file"] = None
        self.revision_storage.data["comments_editor"] = ""
        self.revision_storage.save()


@dataclasses.dataclass
class SetupRevisionStorageFull(BaseSetupRevisionStorage):
    revision_flow_type: RevisionStorage.RevisionFlowType = RevisionStorage.RevisionFlowType.FULL

    def _populate_storage(self):
        self.revision_storage.data["submission_requirements"] = False
        self.revision_storage.data["cover_letter_file"] = None
        self.revision_storage.data["comments_editor"] = ""
        # STEP4
        self.revision_storage.data["collaboration_relation"] = (
            ArticleCollaboration.objects.filter(article=self.revision_storage.article)
            .values_list("relation", flat=True)
            .first()
        ) or CollaborationRelation.NONE
        self.revision_storage.data["correspondence_author"] = self.revision_storage.article.correspondence_author.pk
        self.revision_storage.data["owner"] = self.revision_storage.article.owner.pk
        self.revision_storage.data["affiliation_country"] = getattr(
            getattr(self.revision_storage.article, "submission_data", None), "affiliation_country_id", None
        )
        self.revision_storage.data["article_authors"] = list(
            self.revision_storage.article.authors.values_list("id", flat=True)
        )
        self.revision_storage.save()

    def _populate_additional_models(self):
        article_author = ArticleAuthorOrder.objects.filter(article=self.revision_storage.article)
        for aa in article_author:
            RevisionArticleAuthorOrder.objects.get_or_create(
                revision_storage=self.revision_storage,
                author=aa.author,
                order=aa.order,
            )

        article_collaboration = ArticleCollaboration.objects.filter(article=self.revision_storage.article)
        for ac in article_collaboration:
            RevisionArticleCollaboration.objects.get_or_create(
                revision_storage=self.revision_storage,
                collaboration=ac.collaboration,
                relation=ac.relation,
                order=ac.order,
            )
