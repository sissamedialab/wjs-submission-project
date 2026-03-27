import dataclasses
import xml

import defusedxml
import requests
from core import files as core_files
from core.models import Account
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.text import format_lazy
from identifiers.models import Identifier
from journal.models import Journal
from submission.models import STAGE_REJECTED, STAGE_UNSUBMITTED, Article, ArticleAuthorOrder
from utils.setting_handler import get_setting

from .conversion import start_source_conversion

ARXIV_API_URL = "https://export.arxiv.org/api/query?id_list={}"


class ArXivQueryError(Exception):
    """Raised when the initial arXiv query fails."""

    def __init__(self, message: str):
        """
        Represent an exception raised for errors related to an ArXiv query.

        This exception indicates that an issue occurred while processing an ArXiv query,
        providing the associated error message for further context on the failure.

        :param message: The error message detailing the query issue.
        :type message: str
        """
        super().__init__(f"{message}")
        self.message = message


class ArXivIDAlreadyUsedError(ArXivQueryError):
    """Raised when and Article with the same arXiv ID or with the same metadata already exists."""

    def __init__(
        self,
        message: str = "this preprint has already been submitted to the Journal. Please contact the "
        "Editorial Office from the article web page for assistance.",
    ):
        """
        Initialize the exception with a default or custom message.

        :param message: A message describing the exception.
        :type message: str
        """
        super().__init__(message=message)


class ArXivIDNotFoundError(ArXivQueryError):
    """Raised when the given arXiv ID is syntactically valid but not found."""

    def __init__(
        self,
        message: str = "the arXiv id you have entered cannot be found on arxiv.org",
    ):
        """
        Initialize a custom exception used for handling cases where an arXiv ID cannot be found on arxiv.org.

        :param message: Optional custom error message to specify details regarding the
            unmatched arXiv ID.
        """
        super().__init__(message=message)


class ArXivConnectionError(ArXivQueryError):
    """Raised when connection to the arXiv API fails (timeout, DNS, etc)."""

    def __init__(self, message: str = "connection to arXiv could not be established."):
        """
        Represent an exception raised when a connection to arXiv could not be established.

        This exception is a subclass of the base exception and is intended to inform the
        user of connection-related issues specifically when interacting with the arXiv
        platform. The exception allows for a custom message to be passed during
        initialization.

        :param message: The error message describing the connection failure (default is
            "Connection to arXiv could not be established.").
        :type message: str
        """
        super().__init__(message=message)


class ArXivCorruptedDataError(ArXivQueryError):
    """Raised when the arXiv API returns corrupted data."""

    def __init__(self, message: str | None = None):
        """
        Represent an exception that is raised when corrupted data from arXiv is encountered.

        :param message: A message indicating the reason for the exception.
        :type message: str
        """
        super().__init__(message=message)


class GenericArxivError(ArXivQueryError):
    """Raised when an unexpected error occurs while fetching metadata from the arXiv API."""

    def __init__(self, message: str | None = None):
        """
        Represent a mechanism to initialize an object with an optional message.

        :param message: An optional string that represents the message for this instance.
        :type message: str, optional
        """
        super().__init__(message=message)


def fetch_arxiv_metadata(arxiv_id: str) -> tuple[dict, dict]:
    """
    Fetch metadata for a given arXiv ID from the arXiv API.

    This function retrieves metadata related to a specific scientific paper
    by querying the arXiv API. It parses the XML response from the API to
    extract details such as the title, abstract, and category. Additionally,
    it attempts to download the source file associated with the paper.

    If the arXiv ID is invalid or any issues occur during the API call or
    data parsing, exceptions will be raised accordingly.

    :param arxiv_id: The arXiv ID of the paper to query.
    :type arxiv_id: str
    :return: A tuple containing:
             1. A dictionary with keys such as "title", "abstract",
                "category_term", "source_file", "arxiv_id", and "doi_link".
                Missing values are represented as None or an empty string.
             2. A dictionary of errors that were encountered while downloading
                or processing the source file.
    :rtype: tuple[dict, dict]
    :raises ArXivIDNotFoundError: If the arXiv ID is invalid or not found in
                                  the API response.
    :raises ArXivQueryError: If an expected XML element is missing or the XML
                             response cannot be parsed.
    :raises ArXivConnectionError: If there is a network-related issue or the
                                  arXiv API cannot be reached.
    """
    errors: dict[str, str] = {}
    result: dict[str, str | None] = {
        "title": None,
        "abstract": None,
        "category_term": None,
        "source_file": None,
        "arxiv_id": None,
        "doi_link": None,
    }

    try:
        url = ARXIV_API_URL.format(arxiv_id)
        headers = {
            "Accept": "*/*",
            "Connection": "close",
        }  # TODO: do we want something more specific?
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()

        root = defusedxml.ElementTree.fromstring(r.text)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        entry = root.find("atom:entry", ns)

        title_elem = entry.find("atom:title", ns) if entry is not None else None
        if entry is None or title_elem is None or not title_elem.text.strip():
            raise ArXivIDNotFoundError  # noqa: TRY301

        abstract_elem = entry.find("atom:summary", ns)
        category_elem = entry.find("arxiv:primary_category", ns)
        id_elem = entry.find("atom:id", ns)
        full_id = id_elem.text.strip()
        doi_elem = entry.find('atom:link[@title="doi"]', ns)

        result["title"] = title_elem.text
        result["abstract"] = abstract_elem.text
        result["category_term"] = category_elem.attrib.get("term")
        result["arxiv_id"] = full_id.rsplit("/", 1)[-1]
        if (
            doi_elem is not None
            and isinstance(doi_elem, xml.etree.ElementTree.Element)
            and doi_elem.attrib.get("href")
        ):
            result["doi_link"] = doi_elem.attrib.get("href")
    except (AttributeError, defusedxml.ElementTree.ParseError) as e:
        raise ArXivCorruptedDataError from e
    except requests.exceptions.RequestException as e:
        # The following error will never be shown by the microservice because It's overriden with a message
        # containing the Journal's email and information for the user
        if getattr(e, "response", None) and getattr(e.response, "content", None):
            msg = f"Connection to arXiv could not be established: {e.response.content.decode()}"
        else:
            msg = f"Connection to arXiv could not be established: {e!s}"
        raise ArXivConnectionError(msg) from e
    except ArXivQueryError:
        # If exception is already a ArXivQueryError no need to wrap it around ArXivQueryError again
        raise
    except Exception as e:
        raise GenericArxivError from e

    # ATM we take only the source file so we don't really need a dictionary for file and errors, on the other hand in
    # this way of handling could be helpful if in the future we want to handle multiple files
    file_name, base_url = "source_file", "https://arxiv.org/src/{}"
    url = base_url.format(arxiv_id)
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            result[file_name] = resp.content
        else:
            errors[file_name] = f"HTTP {resp.status_code}"
    except Exception as e:  # noqa: BLE001
        errors[file_name] = str(e)

    return result, errors


@dataclasses.dataclass
class ArXivToArticle:
    """
    Fetch, validate, and create articles from arXiv metadata, optionally attach source files to the created articles.

    :ivar arxiv_id: The arXiv ID for fetching metadata.
    :type arxiv_id: str
    :ivar arxiv_article_id: The ID of the article being submitted, 0 if it's a new article.
    :type arxiv_article_id: int
    :ivar journal: The journal context for article creation and validation.
    :type journal: Journal
    :ivar user: The account initiating the article creation process.
    :type user: Account
    """

    arxiv_id: str
    arxiv_article_id: int
    journal: Journal
    user: Account

    @staticmethod
    def _get_article_candidates(response_content: dict, journal: Journal) -> QuerySet:
        """
        Retrieve article candidates based on the provided response content.

        Matches articles using either the 'arxiv_id', title, abstract, or identifiers already associated with articles.

        :param response_content: A dictionary containing 'arxiv_id', 'title',
            and 'abstract' keys to filter candidate articles.
        :type response_content: dict
        :param journal: The Journal instance to filter candidates by.
        :type journal: Journal
        :return: A queryset of Article objects that match the given criteria.
        :rtype: QuerySet
        :raises KeyError: If required keys ('arxiv_id', 'title', 'abstract') are missing in
            the response_content.
        """
        articles_by_identifier = Identifier.objects.filter(
            identifier=response_content["arxiv_id"],
            id_type="arxiv",
            article__isnull=False,
        ).values_list("article", flat=True)
        return Article.objects.filter(journal=journal).filter(
            Q(
                title__iexact=response_content["title"],
                abstract__iexact=response_content["abstract"],
            )
            | Q(pk__in=articles_by_identifier),
        )

    def _check_article_unique(self, response_content: dict, journal: Journal) -> None:
        """
        Raise an exception if the metadata for the given arXiv ID or title/abstract already exists in the database.

        Checks:
        - An Article with the same ArXiv ID already exists and state not in (withdrawn, unsubmitted)
        - An Article with the same title and abstract already exists and state not in (withdrawn, unsubmitted)

        :param response_content: A dictionary containing 'arxiv_id', 'title',
            and 'abstract' keys to filter candidate articles.
        :type response_content: dict
        :param journal: The Journal instance to filter candidates by.
        :type journal: Journal
        :raises ArXivIDAlreadyUsedError: If an article with the same arXiv ID or title/abstract already exists.
        """
        # FIXME: Make this check pluggable and provide a base implementation in wjs-submission and create a logic
        #   in wjs_review, where we can use ArticleWorkflow.ReviewStates for checking the states
        #   if identifier.article.articleworkflow.state not in {
        #       ArticleWorkflow.ReviewStates.WITHDRAWN,
        #       ArticleWorkflow.ReviewStates.INCOMPLETE_SUBMISSION,
        #   }:
        #   See https://gitlab.sissamedialab.it/wjs/specs/-/issues/1809

        filtered_articles = self._get_article_candidates(response_content, journal).exclude(
            # Unsubmitted / rejected articles can be re-submitted under new ID
            Q(stage__in={STAGE_UNSUBMITTED, STAGE_REJECTED})
            |
            # If current step is 0, it's an article which just have been created via ArxivMicroservice
            Q(current_step=0)
            |
            # current article being submitted (this is an edit of an existing incomplete submission)
            Q(pk=self.arxiv_article_id)
        )
        if filtered_articles.exists():
            raise ArXivIDAlreadyUsedError

    def _get_or_create_article(self, response_content: dict) -> Article:
        """
        Retrieve or create an `Article` instance based on the given response content.

        If an article with the specified criteria does not exists yet a new article is created and initialized using
        the provided response content and metadata.
        If it already exists (in submission stage) and the article id does not match the current article id, the user
        is redirected to the article submission continuation, else it article object is "recycled" and returned.

        Created article is forced to:
        - stage=STAGE_UNSUBMITTED
        - current_step=0

        :param response_content: A dictionary containing article metadata such as title, abstract, arXiv ID, DOI link,
            and category term.
        :type response_content: dict
        :return: The retrieved or newly created `Article` instance.
        :rtype: Article
        :raises KeyError: If required keys like "title", "abstract", "arxiv_id", or "category_term" are missing from
            the `response_content`.
        """
        candidates = self._get_article_candidates(response_content, self.journal)
        in_submission = candidates.filter(stage__in={STAGE_UNSUBMITTED}, owner=self.user)
        new_article = in_submission.first()
        # this check verify if the recovered article is the current one which we let continue, or the
        # current article is a different one (or a brand new submission in case self.arxiv_article_id is 0)
        if new_article and new_article.pk != self.arxiv_article_id:
            # If the new article submission has moved past the first step, we provide a link to continue the submission
            if new_article.current_step > 0:
                url = reverse("wjs_submission_continue", kwargs={"article_id": new_article.pk})
                msg = format_lazy(
                    'A submission for the current ArXiv ID has already been started, please <a class="text-white" '
                    'href="{url}">complete the existing submission</a>',
                    url=url,
                )
                raise GenericArxivError(msg)
            # is the submission has not gone past step 1, we delete the "phantom" article and create a new one
            new_article.delete()
            new_article = None

        service = HandleArticleCreation(
            user=self.user,
            form_data=response_content,
            journal=self.journal,
            article=new_article,
        )
        return service.run()

    def _attach_source_file(self, article, archive_bytes):
        django_file = File(ContentFile(archive_bytes), name=f"arXiv-source-{article.pk}.tar.gz")

        file_instance = core_files.save_file_to_article(
            django_file,
            article,
            self.user,
        )
        for f in article.source_files.all():
            f.delete()
        article.source_files.add(file_instance)

    def run(self):
        """
        Fetch metadata for a specified arXiv ID, validates it, creates an article and identifier.

        Optionally attaches the source file if available and valid.

        This method performs atomic operations ensuring that all or none of the changes
        are applied to the database in the event of an error. Metadata is fetched from the arXiv,
        checked for uniqueness if required, and used to generate an Article object. If the metadata
        includes a valid source file and no errors are detected for the file, it is attached to the
        created article.

        This process ensures data integrity and handles errors gracefully, either by raising specific
        exceptions or reverting changes when necessary.

        :raises ArXivConnectionError: If a connection to the arXiv could not be established.
        :param self: The class instance running the method.
        :return: Created Article object.
        """
        with transaction.atomic():
            try:
                result, file_errors = fetch_arxiv_metadata(self.arxiv_id)
            except ArXivConnectionError as e:
                from_email = get_setting("general", "support_email", self.journal).processed_value
                msg = format_lazy(
                    "Connection to arXiv could not be established. Please try again later or contact {from_email}"
                    " for assistance",
                    from_email=from_email,
                )
                raise ArXivConnectionError(msg) from e
            except ArXivCorruptedDataError as e:
                from_email = get_setting("general", "support_email", self.journal).processed_value
                msg = format_lazy(
                    "Corrupted data from arXiv. Contact the Journal for assistance ({from_email}",
                    from_email=from_email,
                )
                raise ArXivConnectionError(msg) from e
            except GenericArxivError as e:
                from_email = get_setting("general", "support_email", self.journal).processed_value
                msg = format_lazy("Please contact the Journal for assistance ({from_email}", from_email=from_email)
                raise GenericArxivError(msg) from e
            self._check_article_unique(result, self.journal)

            article = self._get_or_create_article(result)

            # TODO (maybe): refactor string "source_file" into a constant?
            #      It must agree between here and inside fetch_arxiv_metadata()
            if result["source_file"] and not file_errors.get("source_file", None):
                self._attach_source_file(article, result["source_file"])

        return article


@dataclasses.dataclass
class ArXivToWjsArticle:
    """
    Handle the conversion of an arXiv article to a format compatible with a specific journal and user.

    This class facilitates the transformation of an arXiv article, using the provided article data,
    the journal settings, and the user who initiated the conversion process.

    :ivar arxiv_id: The arXiv identifier for the article.
    :type arxiv_id: str
    :ivar arxiv_article_id: The ID of the article being submitted, 0 if it's a new article.
    :type arxiv_article_id: int
    :ivar request: The HTTP request containing journal and user information.
    :type request: HttpRequest
    """

    arxiv_id: str
    arxiv_article_id: int
    request: HttpRequest

    def _convert_source_archive(self, article: Article):
        start_source_conversion(article, self.request, article.source_files.first())

    def run(self):
        """
        Execute the process to convert an arXiv article to the desired format linked to a specific journal and user.

        The method initializes the conversion process, updates the article's current step, saves it, and processes
        the first available source file.

        :return: Returns the processed article object.
        :rtype: Article
        """
        article = ArXivToArticle(
            arxiv_id=self.arxiv_id,
            arxiv_article_id=self.arxiv_article_id,
            journal=self.request.journal,
            user=self.request.user,
        ).run()
        if article.source_files.first():
            self._convert_source_archive(article)
        return article


@dataclasses.dataclass
class HandleArticleCreation:
    user: Account
    form_data: dict
    journal: Journal
    article: Article | None = None

    def _create_article(self) -> Article:
        base_data = {}
        if self.article:
            base_data = {k: v for k, v in self.article.__dict__.items() if k != "_state" and v}
        base_data.update(
            {
                "journal": self.journal,
                "title": self.form_data.get("title", ""),
                "abstract": self.form_data.get("abstract", ""),
                "correspondence_author": self.user,
                "owner": self.user,
                "stage": STAGE_UNSUBMITTED,
                "current_step": 0,
            }
        )
        new_article = Article.objects.create(**base_data)
        ArticleAuthorOrder.objects.get_or_create(
            article=new_article,
            author=self.user,
            defaults={"order": 0},
        )
        new_article.authors.add(self.user)
        return new_article

    def _set_arxiv_metadata(self):
        Identifier.objects.get_or_create(
            # Here we don't use self.arxiv_id but we use the one we get from the API payload because the
            # latter contains also the version number
            identifier=self.form_data.get("arxiv_id"),
            article=self.article,
            id_type="arxiv",
        )

        if self.form_data.get("doi_link"):
            Identifier.objects.get_or_create(
                identifier=self.form_data["doi_link"],
                article=self.article,
                id_type="doi",
            )
        if self.form_data.get("category_term"):
            self.article.submission_data.arxiv_category = self.form_data["category_term"]
        self.article.submission_data.save()

    def run(self):
        """
        Ensure the user has the "author" role in the context of the specified journal and get / create an article.

        :raises PermissionError: If the user does not have sufficient permissions.
        :param self: The instance of the class that contains this method.
        :return: An instance of an article, either newly created or retrieved from the database.
        :rtype: Article
        """
        if not self.user.check_role(self.journal, "author", staff_override=False):
            self.user.add_account_role("author", self.journal)

        if not self.article or not self.article.pk:
            self.article = self._create_article()
            if self.form_data.get("arxiv_id"):
                self._set_arxiv_metadata()
        return self.article
