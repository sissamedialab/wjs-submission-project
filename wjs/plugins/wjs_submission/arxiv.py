import dataclasses
import io
import os
import tarfile
import xml.etree.ElementTree as ET  # noqa

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
from wjs.jcom_profile import permissions as base_permissions


class ArXivQueryError(Exception):
    """Raised when the initial arXiv query fails."""

    def __init__(self, message: str):
        super().__init__(f"ArXiv query error: {message}")
        self.message = message


class ArXivIDAlreadyUsed(ArXivQueryError):
    """Raised when and Article with the same arXiv ID or with the same metadata already exists."""

    def __init__(self):
        super().__init__("The arXiv ID must not already be in use")


class ArXivIDNotFoundError(ArXivQueryError):
    """Raised when the given arXiv ID is syntactically valid but not found."""

    def __init__(self):
        super().__init__("The arXiv id you have entered cannot be found on arxiv.org")


class ArXivConnectionError(ArXivQueryError):
    """Raised when connection to the arXiv API fails (timeout, DNS, etc)."""

    def __init__(self, message: str = "Connection to arXiv could not be established. "):
        super().__init__(message)


def fetch_arxiv_metadata(arxiv_id: str) -> tuple[dict, dict]:
    """
    Query arXiv and retrieve metadata and source files.

    Return:
       - result: metadata dict with keys title, abstract, category_term, source_file, pdf_file
       - errors: dict of any file‐download errors

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
        url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
        headers = {
            "Accept": "*/*",
            "Connection": "close",
        }  # TODO: do we want something more specific?
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        xml_content = r.text

        root = ET.fromstring(xml_content)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        entry = root.find("atom:entry", ns)

        title_elem = entry.find("atom:title", ns) if entry is not None else None
        if entry is None or title_elem is None or not title_elem.text.strip():
            raise ArXivIDNotFoundError

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
            result["doi_link"] = ET.tostring(doi_elem, encoding="unicode")

    except AttributeError as e:
        raise ArXivQueryError(f"Missing expected element in arXiv response: {e}") from e
    except requests.exceptions.RequestException as e:
        # The following error will never be shown by the microservice because It's overriden with a message
        # containing the Journal's email and information for the user
        if getattr(e, "response", None) and getattr(e.response, "content", None):
            msg = e.response.content.decode()
        else:
            msg = str(e)
        raise ArXivConnectionError(f"Connection to arXiv could not be established: {msg}") from e
    except ET.ParseError as e:
        raise ArXivQueryError(f"XML parse error: {e}") from e
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
    except Exception as e:
        errors[file_name] = str(e)

    return result, errors


class MockExternalPDFService:
    """
    Mock external PDF generation service.

    This class simulates an external service that processes a source archive
    (tar.gz) bytes and returns a dummy PDF stored in the project.
    """

    def __init__(self, dummy_pdf_path: str):
        # Path to the dummy PDF to return
        self.dummy_pdf_path = dummy_pdf_path

    def process_archive(self, archive_content: bytes) -> bytes:
        """
        Process the given source archive content and return PDF content.

        Args:
            archive_content: bytes of the .tar.gz archive

        Returns:
            Bytes of the dummy PDF file.

        """
        try:
            with tarfile.open(fileobj=io.BytesIO(archive_content), mode="r:gz"):
                pass
        except Exception as e:
            raise ValueError(f"Invalid archive provided: {e}")

        try:
            with open(self.dummy_pdf_path, "rb") as pdf_file:
                return pdf_file.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Dummy PDF not found at {self.dummy_pdf_path}")


@dataclasses.dataclass
class ArXivToArticle:
    arxiv_id: str
    journal: Journal
    user: Account
    check_unique: bool = True

    def _check_article_unique(self, response_content: dict):
        """
        Return False when one of the following is True:
            - An Article with the same ArXiv ID already exists and state not in (withdrawn, incomplete submissions)
            - An Article with the same title and abstract already exists and
              state not in (withdrawn, incomplete submissions)
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
                raise ArXivIDAlreadyUsed
        except Identifier.DoesNotExist:
            pass

        if Article.objects.filter(
            title__iexact=response_content["title"],
            abstract__iexact=response_content["abstract"],
        ).exists():
            raise ArXivIDAlreadyUsed

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
        new_article.articleworkflow.arxiv_category = result["category_term"]
        new_article.articleworkflow.save()

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
        with transaction.atomic():
            try:
                result, file_errors = fetch_arxiv_metadata(self.arxiv_id)
            except ArXivConnectionError:
                from_email = get_setting("general", "main_contact", self.journal).processed_value
                raise ArXivConnectionError(
                    "Connection to arXiv could not be established. "
                    f"Please try again or contact {from_email} for assistance"
                )

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

    def _convert_source_archive(self, source_file_bytes: bytes) -> bytes:
        base_dir = os.path.dirname(__file__)
        dummy_pdf_path = os.path.join(base_dir, "files", "arxiv_pdf_sample.pdf")
        # TODO: this is just an example mock, the real implementation won't return anything since It will be
        # asynchronous
        service = MockExternalPDFService(dummy_pdf_path=str(dummy_pdf_path))
        pdf_bytes = service.process_archive(source_file_bytes)
        return pdf_bytes

    def run(self):
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
        if not base_permissions.has_author_role(self.journal, self.user):
            self.user.add_account_role("author", self.journal)

        if not self.article_id:
            new_article = self._create_article()
        else:
            new_article = Article.objects.get(pk=self.article_id)

        return new_article
