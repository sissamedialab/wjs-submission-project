import dataclasses
import io
import tarfile
from pathlib import Path

import defusedxml
import requests
from core import files as core_files
from core.models import Account
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import transaction
from identifiers.models import Identifier
from journal.models import Journal
from submission.models import STAGE_REJECTED, STAGE_UNSUBMITTED, Article
from utils.setting_handler import get_setting

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
        super().__init__(f"ArXiv query error: {message}")
        self.message = message


class ArXivIDAlreadyUsedError(ArXivQueryError):
    """Raised when and Article with the same arXiv ID or with the same metadata already exists."""

    def __init__(self, message: str = "The arXiv ID must not already be in use."):
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
        message: str = "The arXiv id you have entered cannot be found on arxiv.org",
    ):
        """
        Initialize a custom exception used for handling cases where an arXiv ID cannot be found on arxiv.org.

        :param message: Optional custom error message to specify details regarding the
            unmatched arXiv ID.
        """
        super().__init__(message=message)


class ArXivConnectionError(ArXivQueryError):
    """Raised when connection to the arXiv API fails (timeout, DNS, etc)."""

    def __init__(self, message: str = "Connection to arXiv could not be established."):
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
        if doi_elem is not None:
            result["doi_link"] = defusedxml.ElementTree.tostring(doi_elem, encoding="unicode")

    except AttributeError as e:
        msg = f"Missing expected element in arXiv response: {e}"
        raise ArXivQueryError(msg) from e
    except requests.exceptions.RequestException as e:
        # The following error will never be shown by the microservice because It's overriden with a message
        # containing the Journal's email and information for the user
        if getattr(e, "response", None) and getattr(e.response, "content", None):
            msg = f"Connection to arXiv could not be established: {e.response.content.decode()}"
        else:
            msg = f"Connection to arXiv could not be established: {e!s}"
        raise ArXivConnectionError(msg) from e
    except defusedxml.ElementTree.ParseError as e:
        msg = f"XML parse error: {e}"
        raise ArXivQueryError(msg) from e
    except Exception as e:
        raise ArXivQueryError(str(e)) from e

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


class MockExternalPDFService:
    """
    Mock external PDF generation service.

    This class simulates an external service that processes a source archive
    (tar.gz) bytes and returns a dummy PDF stored in the project.
    """

    def __init__(self, dummy_pdf_path: str):
        """
        Initialize an instance with a provided path to a dummy PDF.

        The provided path is used to manage or reference a dummy PDF file
        for specific operations.

        :param dummy_pdf_path: The file system path to the dummy PDF.
        :type dummy_pdf_path: str
        """
        self.dummy_pdf_path = Path(dummy_pdf_path)

    def process_archive(self, archive_content: bytes) -> bytes:
        """
        Process the given source archive content and return PDF content.

        :param archive_content: Bytes of the .tar.gz archive
        :return: Bytes of the dummy PDF file.
        """
        try:
            with tarfile.open(fileobj=io.BytesIO(archive_content), mode="r:gz"):
                pass
        except Exception as e:
            msg = f"Invalid archive provided: {e}"
            raise ValueError(msg) from e

        try:
            with self.dummy_pdf_path.open("rb") as pdf_file:
                return pdf_file.read()
        except FileNotFoundError as e:
            msg = f"Dummy PDF not found at {self.dummy_pdf_path}"
            raise FileNotFoundError(msg) from e


@dataclasses.dataclass
class ArXivToArticle:
    arxiv_id: str
    journal: Journal
    user: Account
    check_unique: bool = True

    @staticmethod
    def _check_article_unique(response_content: dict) -> None:
        """
        Raise an exception if the metadata for the given arXiv ID already exists in the database.

        Checks:
        - An Article with the same ArXiv ID already exists and state not in (withdrawn, unsubmitted)
        - An Article with the same title and abstract already exists and state not in (withdrawn, unsubmitted)
        """
        # TODO: We will need to move this logic in a class of its own because we will need in other parts of
        #  the submission process
        try:
            identifier = Identifier.objects.get(
                identifier=response_content["arxiv_id"],
                id_type="arxiv",
                article__isnull=False,
            )
            if identifier.article.stage not in {
                STAGE_UNSUBMITTED,
                STAGE_REJECTED,
            }:
                raise ArXivIDAlreadyUsedError
        except Identifier.DoesNotExist:
            pass

        if Article.objects.filter(
            title__iexact=response_content["title"],
            abstract__iexact=response_content["abstract"],
        ).exists():
            raise ArXivIDAlreadyUsedError

    def _create_article_and_identifier(self, result):
        # ATM the owner and correspondence_author is the submitting user, in a later stage this can be changed
        new_article = Article.objects.create(
            journal=self.journal,
            owner=self.user,
            title=result["title"],
            abstract=result["abstract"],
            correspondence_author=self.user,
        )
        new_article.authors.add(self.user)

        Identifier.objects.create(
            # Here we don't use self.arxiv_id but we use the one we get from the API payload because the
            # latter contains also the version number
            identifier=result["arxiv_id"],
            article=new_article,
            id_type="arxiv",
        )

        if result["doi_link"]:
            Identifier.objects.create(
                identifier=result["doi_link"],
                article=new_article,
                id_type="doi",
            )
        new_article.submission_data.arxiv_category = result["category_term"]
        new_article.submission_data.save()

        return new_article

    def _attach_source_file(self, article, archive_bytes):
        django_file = File(ContentFile(archive_bytes), name=f"arXiv-source-{article.pk}.tar.gz")

        file_instance = core_files.save_file_to_article(
            django_file,
            article,
            self.user,
        )
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
                from_email = get_setting("general", "main_contact", self.journal).processed_value
                msg = (
                    f"Connection to arXiv could not be established. "
                    f"Please try again or contact {from_email} for assistance"
                )
                raise ArXivConnectionError(msg) from e

            if self.check_unique:
                self._check_article_unique(result)

            article = self._create_article_and_identifier(result)

            # TODO (maybe): refactor string "source_file" into a constant?
            #      It must agree between here and inside fetch_arxiv_metadata()
            if result["source_file"] and not file_errors.get("source_file", None):
                self._attach_source_file(article, result["source_file"])

        return article


@dataclasses.dataclass
class ArXivToWjsArticle:
    arxiv_id: str
    journal: Journal
    user: Account

    @staticmethod
    def _convert_source_archive(source_file_bytes: bytes) -> bytes:
        base_dir = Path(__file__).parent
        dummy_pdf_path = base_dir / "files" / "arxiv_pdf_sample.pdf"
        # TODO: this is just an example mock, the real implementation won't return anything since It will be
        # asynchronous
        service = MockExternalPDFService(dummy_pdf_path=str(dummy_pdf_path))
        return service.process_archive(source_file_bytes)

    def run(self):
        """
        Execute the process to convert an arXiv article to the desired format linked to a specific journal and user.

        The method initializes the conversion process, updates the article's current step, saves it, and processes
        the first available source file.

        :return: Returns the processed article object.
        :rtype: Article
        """
        article = ArXivToArticle(arxiv_id=self.arxiv_id, journal=self.journal, user=self.user).run()

        article.current_step = 0
        article.save()
        if source_file := article.source_files.first():
            self._convert_source_archive(source_file.get_file(article, as_bytes=True))

        return article


@dataclasses.dataclass
class HandleArticleCreation:
    user: Account
    form_data: dict
    journal: Journal
    article_id: None

    def _create_article(self):
        new_article = Article.objects.create(
            journal=self.journal,
            correspondence_author=self.user,
            owner=self.user,
            language="eng",
            current_step=0,
        )
        new_article.authors.add(self.user)
        return new_article

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

        if not self.article_id:
            new_article = self._create_article()
        else:
            new_article = Article.objects.get(pk=self.article_id)

        return new_article
