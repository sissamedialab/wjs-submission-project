"""
Logic for the correction (erratum/addendum) submission workflow.

This module contains the :class:`SetupCorrectionStorage` dataclass that creates
and pre-populates a new correction article linked to a published article via the
Hydra ``LinkedArticle`` model.
"""

import dataclasses
from typing import Literal

from django.db.transaction import atomic
from identifiers.models import Identifier
from plugins.hydra.models import LinkedArticle
from submission.models import (
    STAGE_ARCHIVED,
    STAGE_PUBLISHED,
    STAGE_REJECTED,
    STAGE_UNSUBMITTED,
    Article,
    FrozenAuthor,
    Section,
)

from ..models import (
    AccessMode,
    AccessModeJournal,
    ArticleCollaboration,
    ArticleSubmission,
)
from .links import article_children

# Relationship labels (matching Hydra LinkType values).
ERRATUM = "erratum"
ADDENDUM = "addendum"
CORRECTION_RELATIONSHIPS = (ERRATUM, ADDENDUM)

CORRECTION_RELATIONSHIPS_TYPES = Literal[ERRATUM, ADDENDUM]

# Section names corresponding to each relationship.
SECTION_NAME_BY_RELATIONSHIP = {
    ERRATUM: "Erratum",
    ADDENDUM: "Addendum",
}


# Set of section names that identify correction articles.
CORRECTION_SECTION_NAMES = set(SECTION_NAME_BY_RELATIONSHIP.values())


@dataclasses.dataclass
class SetupCorrectionStorage:
    """
    Create or resume a correction (erratum/addendum) article linked to a published article.

    Following the :class:`BaseSetupRevisionStorage` pattern from
    ``revision/logic.py``, this dataclass:

    - Retrieves the published ``from_article``.
    - Creates or resumes a new ``to_article`` (the correction).
    - Links them via Hydra ``LinkedArticle``.
    - Pre-populates the correction article with metadata from ``from_article``.
    """

    article_id: int
    """The PK of the published article (``from_article``)."""

    relationship: str
    """Either ``"erratum"`` or ``"addendum"``."""

    request: object | None = None
    """The HTTP request (used to determine the owner). May be ``None`` in tests."""

    from_article: Article = dataclasses.field(init=False)
    to_article: Article = dataclasses.field(init=False)
    created: bool = dataclasses.field(init=False, default=False)

    def _get_from_article(self) -> Article:
        return Article.objects.get(pk=self.article_id)

    def _check_conditions(self, article: Article) -> bool:
        """Check that the from_article is published and the user is an author."""
        if article.stage != STAGE_PUBLISHED:
            return False
        # Authorization: only authors/co-authors/owner of the from_article can
        # start a correction.
        user = getattr(self.request, "user", None)
        if user is None:
            return False
        return (
            user in (article.owner, article.correspondence_author)
            or article.frozen_authors().filter(author=user).exists()
        )

    def _get_section(self) -> Section:
        """Get the Erratum or Addendum section for the from_article's journal."""
        section_name = SECTION_NAME_BY_RELATIONSHIP[self.relationship]
        return Section.objects.get(
            journal=self.from_article.journal,
            name=section_name,
        )

    def _get_or_create_correction_article(self) -> Article:
        """
        Create or resume the correction article linked to from_article.

        - If a Hydra ``LinkedArticle`` with the same relationship already exists
          and its ``to_article`` is in-progress (stage UNSUBMITTED):
          - if the existing correction's owner != request.user -> raise ValueError
          - if the existing correction's owner == request.user -> return it (resume)
        - Otherwise create a new Article (to_article):
          - stage = STAGE_UNSUBMITTED
          - owner = request.user
          - journal = from_article.journal
          - section = Erratum or Addendum section
          - arXiv identifier copied from from_article (if available)
        """
        section = self._get_section()

        # Check if a correction of the same type already exists and is in-progress.
        existing = self._find_existing_correction()
        if existing is not None:
            user = getattr(self.request, "user", None)
            if existing.owner != user:
                kind = self.relationship.capitalize()
                raise ValueError(
                    f"Someone is already submitting a {kind} for this article.",
                )
            # Resuming an existing correction: do not re-populate or re-link.
            self.created = False
            return existing

        # Create the new correction article.
        user = getattr(self.request, "user", None)
        self.created = True
        to_article = Article.objects.create(
            owner=user,
            journal=self.from_article.journal,
            section=section,
            stage=STAGE_UNSUBMITTED,
            current_step=0,
            correspondence_author=user,
        )

        # Copy arXiv identifier if available.
        from_arxiv = self.from_article.identifiers.filter(id_type="arxiv").first()
        if from_arxiv:
            Identifier.objects.create(
                article=to_article,
                id_type="arxiv",
                identifier=from_arxiv.identifier,
            )

        return to_article

    def _find_existing_correction(self) -> Article | None:
        """Find an existing in-progress correction of the same type for the from_article."""
        stages = (STAGE_ARCHIVED, STAGE_REJECTED)

        articles = article_children(self.from_article, [self.relationship])
        return articles.exclude(stage__in=stages).first()

    def _link_articles(self):
        """Link from_article and to_article via the Hydra LinkedArticle model."""
        get_or_create_linked_article(self.from_article, self.to_article, self.relationship)

    def _populate_metadata(self):
        """
        Pre-populate the correction article with data from from_article.

        - title = "ERRATUM: from_article.title" (or "ERRATUM{N}: ..." if multiple errata)
        - abstract = from_article.abstract
        - keywords = from_article.keywords
        - authors = from from_article's FrozenAuthor records (copied as new FrozenAuthor rows)
        - collaborations = same as from_article
        - access_mode = AccessMode.objects.get(code='open-access')
        - rights = AccessModeJournal for open-access + journal
        - license = from_article.license
        """
        # Compute title before linking to avoid counting self.
        self.to_article.title = get_correction_title(self.from_article, self.relationship)
        self.to_article.license = self.from_article.license
        self.to_article.language = self.from_article.language
        self.to_article.save()

        # Copy keywords.
        for keyword in self.from_article.keywords.all():
            self.to_article.keywords.add(keyword)

        # Create ArticleSubmission wrapper (needed by steps 6/7).
        ArticleSubmission.objects.get_or_create(article=self.to_article)

        # Set access_mode and rights.
        try:
            access_mode = AccessMode.objects.get(code="open-access")
            self.to_article.submission_data.access_mode = access_mode
            self.to_article.submission_data.save()

            access_mode_journal = AccessModeJournal.objects.filter(
                access_mode=access_mode,
                journal=self.from_article.journal,
            ).first()
            if access_mode_journal:
                self.to_article.license = access_mode_journal.licence
                self.to_article.rights = access_mode_journal.copyright
                self.to_article.save()
        except AccessMode.DoesNotExist:
            pass

        # Copy authors: create FrozenAuthor records for the correction article
        # (corrections skip step 4 which normally creates them).
        frozen_authors = FrozenAuthor.objects.filter(article=self.from_article)
        for frozen_author in frozen_authors:
            # Create a FrozenAuthor copy for the correction article.
            frozen_author.pk = None
            frozen_author.article = self.to_article
            frozen_author.save()

        # Copy collaborations.
        for collaboration in ArticleCollaboration.objects.filter(article=self.from_article):
            ArticleCollaboration.objects.get_or_create(
                article=self.to_article,
                collaboration=collaboration.collaboration,
                defaults={
                    "relation": collaboration.relation,
                    "order": collaboration.order,
                },
            )

    def run(self):
        """Run the correction setup: create article, populate metadata, then link."""
        self.from_article = self._get_from_article()
        if not self._check_conditions(self.from_article):
            raise ValueError("Cannot start a correction for this article.")
        with atomic():
            self.to_article = self._get_or_create_correction_article()
            if self.created:
                # Only populate metadata and link for new corrections.
                # On resume, the correction is already populated and linked.
                # Populate metadata BEFORE linking so that get_correction_title()
                # does not count the just-created to_article among existing corrections.
                self._populate_metadata()
                self._link_articles()
        return self.to_article


def find_existing_correction(from_article: Article, relationship: str) -> Article | None:
    """
    Find a related correction article for a given relationship type.

    Search for an existing correction article related to the provided article via
    Hydra ``LinkedArticle``. Only in-progress corrections (stage UNSUBMITTED) are
    considered.

    :param from_article: The article for which to find a related correction.
    :type from_article: Article
    :param relationship: The correction type ("erratum" or "addendum").
    :type relationship: str
    :return: A related correction article matching the relationship and stage filter,
        or None if no such article is found.
    :rtype: Article | None
    """
    link = (
        from_article.linked_from.filter(
            relationship=relationship,
            to_article__stage=STAGE_UNSUBMITTED,
        )
        .select_related("to_article")
        .first()
    )
    if link:
        return link.to_article
    return None


def get_correction_title(from_article: Article, relationship: str) -> str:
    """
    Build the title for a correction article.

    For erratum: ``ERRATUM: original.title`` or ``ERRATUM2: original.title`` etc.
    For addendum: ``ADDENDUM: original.title`` or ``ADDENDUM2: ...`` etc.

    The count is based on how many corrections of the same type are already
    linked to ``from_article`` via Hydra ``LinkedArticle``, regardless of their stage.
    """
    prefix = relationship.upper()
    count = from_article.linked_from.filter(relationship=relationship).count()
    if count > 0:
        prefix = f"{prefix}{count + 1}"
    return f"{prefix}: {from_article.title}"


def get_or_create_linked_article(from_article: Article, to_article: Article, relationship: str):
    """
    Link two articles via the Hydra ``LinkedArticle`` model.

    Creates (or retrieves) a ``LinkedArticle`` row so that::

        to_article is a <relationship> of from_article

    For example, an erratum article is a "erratum" of the published paper.

    :param from_article: The original article being corrected.
    :type from_article: Article
    :param to_article: The correction (erratum/addendum) article.
    :type to_article: Article
    :param relationship: The LinkType value ("erratum" or "addendum").
    :type relationship: str
    :return: The ``LinkedArticle`` instance (created or existing).
    :rtype: LinkedArticle
    """
    link, _created = LinkedArticle.objects.get_or_create(
        from_article=from_article,
        to_article=to_article,
        relationship=relationship,
    )
    return link
