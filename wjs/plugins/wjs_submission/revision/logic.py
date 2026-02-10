import dataclasses

from django.db.transaction import atomic
from submission.models import (
    STAGE_UNDER_REVISION,
    Article,
    ArticleAuthorOrder,
)

from ..models import (
    ArticleCollaboration,
    CollaborationRelation,
    RevisionArticleAuthorOrder,
    RevisionArticleCollaboration,
    RevisionStorage,
    RevisionSubmissionArticleFunding,
    SubmissionArticleFunding,
)


@dataclasses.dataclass
class BaseSetupRevisionStorage:
    """
    Base class to create RevisionStorage objects according to the revision flow type.
    """

    article_id: int
    revision_flow_type: RevisionStorage.RevisionFlowType = None
    revision_storage: RevisionStorage = None
    created: bool = False

    def _check_conditions(self) -> bool:
        """
        Check if the article is in a revision stage and if the revision flow type is valid.
        """
        article = Article.objects.get(pk=self.article_id)
        return article.stage == STAGE_UNDER_REVISION

    def _ensure_storage(self):
        """Ensure that the RevisionStorage object exists."""
        self.revision_storage, self.created = RevisionStorage.objects.get_or_create(article_id=self.article_id)
        self.revision_storage.revision_flow_type = self.revision_flow_type

    def _populate_additional_models(self):
        """Create additional models required for the revision flow type."""

    def _populate_storage(self):
        """Populate the RevisionStorage object with data based on the revision flow type."""
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
class PopulateStep1:
    """
    Populate the RevisionStorage object with data for step 1 of the revision flow.

    Reset submission requirements and cover letter fields.
    """

    revision_storage: RevisionStorage

    def __call__(self, commit: bool = False):
        """
        Run the initialization of the RevisionStorage object according to the initialized revision flow.

        :param commit: Save the updated models. Set to True if it's the last step to initialize RevisionStorage.
        :type commit: bool
        """
        self.revision_storage.data["submission_requirements"] = False
        self.revision_storage.data["cover_letter_file"] = None
        self.revision_storage.data["comments_editor"] = ""
        if commit:
            self.revision_storage.save()


@dataclasses.dataclass
class PopulateStep4:
    """
    Populate the RevisionStorage object with data for step 4 of the revision flow.

    Setup the following fields:
    - collaboration_relation
    - correspondence_author
    - owner
    - affiliation_country
    - article_authors
    """

    revision_storage: RevisionStorage

    def __call__(self, commit: bool = False):
        """
        Run the initialization of the RevisionStorage object according to the initialized revision flow.

        :param commit: Save the updated models. Set to True if it's the last step to initialize RevisionStorage.
        :type commit: bool
        """
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
        if commit:
            self.revision_storage.save()


@dataclasses.dataclass
class PopulateStep4AdditionalModels:
    """
    Create additional models required for Step 4.

    Create ArticleAuthorOrder and ArticleCollaboration objects for the article.
    """

    revision_storage: RevisionStorage

    def __call__(self, commit: bool = False):
        """
        Run the initialization of the RevisionStorage object according to the initialized revision flow.

        :param commit: Save the updated models. Set to True if it's the last step to initialize RevisionStorage.
        :type commit: bool
        """
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


@dataclasses.dataclass
class PopulateStep5:
    """
    Populate the RevisionStorage object with data for step 5 of the revision flow.

    Setup the following fields:
    - title
    - abstract
    - section
    - language
    - access_mode
    """

    revision_storage: RevisionStorage

    def __call__(self, commit: bool = False):
        """
        Run the initialization of the RevisionStorage object according to the initialized revision flow.

        :param commit: Save the updated models. Set to True if it's the last step to initialize RevisionStorage.
        :type commit: bool
        """
        self.revision_storage.data["title"] = self.revision_storage.article.title
        self.revision_storage.data["abstract"] = self.revision_storage.article.abstract
        self.revision_storage.data["section"] = self.revision_storage.article.section_id
        self.revision_storage.data["language"] = self.revision_storage.article.language
        if commit:
            self.revision_storage.save()


@dataclasses.dataclass
class PopulateStep7:
    """
    Populate the RevisionStorage object with data for step 7 of the revision flow.

    Setup the following fields:
    - access_mode
    - special_request
    - funding
    """

    revision_storage: RevisionStorage

    def __call__(self, commit: bool = False):
        """
        Run the initialization of the RevisionStorage object according to the initialized revision flow.

        :param commit: Save the updated models. Set to True if it's the last step to initialize RevisionStorage.
        :type commit: bool
        """
        self.revision_storage.data["access_mode"] = self.revision_storage.article.submission_data.access_mode.pk
        self.revision_storage.data["special_request"] = self.revision_storage.article.submission_data.special_request

        fundings = SubmissionArticleFunding.objects.filter(article=self.revision_storage.article)
        for funding in fundings:
            RevisionSubmissionArticleFunding.objects.get_or_create(
                pk=funding.pk,
                revision_storage=self.revision_storage,
                name=funding.name,
                fundref_id=funding.fundref_id,
                funding_id=funding.funding_id,
                funding_statement=funding.funding_statement,
                country=funding.country,
            )

        if commit:
            self.revision_storage.save()


@dataclasses.dataclass
class SetupRevisionStorageConfirm(BaseSetupRevisionStorage):
    """
    Setup the RevisionStorage object for the confirm revision flow type.
    """

    revision_flow_type: RevisionStorage.RevisionFlowType = RevisionStorage.RevisionFlowType.CONFIRM

    def _populate_storage(self):
        """
        Populate the RevisionStorage object with data for step 1 of the revision flow.
        """
        PopulateStep1(self.revision_storage)(commit=True)


@dataclasses.dataclass
class SetupRevisionStorageMetadata(BaseSetupRevisionStorage):
    """
    Setup the RevisionStorage object for the metadata revision flow type.
    """

    revision_flow_type: RevisionStorage.RevisionFlowType = RevisionStorage.RevisionFlowType.METADATA

    def _populate_storage(self):
        """
        Populate the RevisionStorage object with data for step 1, 4 and 5 of the revision flow.
        """
        PopulateStep1(self.revision_storage)()
        PopulateStep4(self.revision_storage)()
        PopulateStep5(self.revision_storage)(commit=True)

    def _populate_additional_models(self):
        """
        Populate additional models required for Step 4.
        """
        PopulateStep4AdditionalModels(self.revision_storage)(commit=True)


@dataclasses.dataclass
class SetupRevisionStorageFull(BaseSetupRevisionStorage):
    """
    Setup the RevisionStorage object for the full revision flow type.
    """

    revision_flow_type: RevisionStorage.RevisionFlowType = RevisionStorage.RevisionFlowType.FULL

    def _populate_storage(self):
        """
        Populate the RevisionStorage object with data for step 1, 4, 5 and 7 of the revision flow.
        """
        PopulateStep1(self.revision_storage)()
        PopulateStep4(self.revision_storage)()
        PopulateStep5(self.revision_storage)()
        PopulateStep7(self.revision_storage)(commit=True)

    def _populate_additional_models(self):
        """
        Populate additional models required for Step 4.
        """
        PopulateStep4AdditionalModels(self.revision_storage)(commit=True)
