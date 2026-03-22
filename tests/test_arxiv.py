import io
import json
import random
import tarfile
import typing
from pathlib import Path

import pytest
import requests
from core import files
from django.core.files import File as DjangoFile
from identifiers.models import Identifier
from plugins.wjs_submission.arxiv import (
    ArXivConnectionError,
    ArXivCorruptedDataError,
    ArXivIDNotFoundError,
    GenericArxivError,
    fetch_arxiv_metadata,
)
from plugins.wjs_submission.views import ArxivMicroservice
from submission.models import STAGE_UNASSIGNED, STAGE_UNSUBMITTED, Article

from .helpers import DummyResponse, make_arxiv_request, mock_requests_get

random.seed(42)

if typing.TYPE_CHECKING:
    from django.http import HttpResponse


@pytest.mark.django_db
def test_fetch_arxiv_metadata_all_success(arxiv_fixtures, monkeypatch):
    metadata_resp = DummyResponse(arxiv_fixtures["xml"], status_code=200, text=arxiv_fixtures["xml"].decode())
    src_resp = DummyResponse(arxiv_fixtures["src"])
    mock_requests_get(
        monkeypatch,
        responses={"api/query": metadata_resp, "/src/": src_resp},
    )

    result, errors = fetch_arxiv_metadata("2504.10562v1")

    assert result["title"].strip()
    assert result["abstract"].strip()
    assert result["category_term"]

    assert result["arxiv_id"] == "2504.10562v1"

    assert result["source_file"] == arxiv_fixtures["src"]
    assert errors == {}


@pytest.mark.django_db
def test_article_creation(arxiv_fixtures, monkeypatch, tmp_path, journal, author, sections):
    """
    Document how to use arXiv to setup an Article.

    Interesting parts in the code are marked with 🌟
    """
    arxiv_id = "1234.5678v1"
    metadata_resp = DummyResponse(arxiv_fixtures["xml"], status_code=200, text=arxiv_fixtures["xml"].decode())
    src_resp = DummyResponse(arxiv_fixtures["src"])
    mock_requests_get(
        monkeypatch,
        responses={"api/query": metadata_resp, "/src/": src_resp},
    )

    result, __ = fetch_arxiv_metadata(arxiv_id)

    date_started = date_submitted = None
    new_article = Article.objects.create(
        abstract=result["abstract"],  # 🌟 use metadata
        journal=journal,
        title=result["title"],  # 🌟
        correspondence_author=author,  # 🌟 ATM, authors are not treated!
        owner=author,
        date_submitted=date_submitted,
        date_started=date_started,
        section=random.choice(sections),  # noqa: S311
        language="eng",
    )
    new_article.authors.add(author)
    # 🌟 Save the arXiv id as an identifier of the article
    Identifier.objects.create(
        identifier=arxiv_id,
        article=new_article,
        id_type="arxiv",
    )

    new_article.submission_data.arxiv_category = result["category_term"]  # 🌟 use metadata
    new_article.submission_data.save()

    assert result["title"] == new_article.title
    assert result["abstract"] == new_article.abstract
    assert arxiv_id == new_article.get_identifier(identifier_type="arxiv")
    assert result["category_term"] == new_article.submission_data.arxiv_category

    # 🌟 Save/attach source files
    # for simplicity, suppose that the archive contains only one .tex file
    tar_gz = io.BytesIO(arxiv_fixtures["src"])
    tar_gz.seek(0)
    with tarfile.open(fileobj=tar_gz, mode="r:gz") as tar:
        member = tar.getmembers()[0]
        tex_bytes = tar.extractfile(member).read()

    django_file = DjangoFile(io.BytesIO(tex_bytes), f"Source-{new_article.pk}.tex")

    file_instance = files.save_file_to_article(
        django_file,
        new_article,
        author,
    )
    new_article.source_files.add(file_instance)

    source_file = new_article.source_files.first()
    with Path(source_file.self_article_path()).open("rb") as f:
        assert f.read() == tex_bytes


@pytest.mark.parametrize(
    ("xml_content", "expected_exc"),
    [
        (b"<invalid><xml>", ArXivCorruptedDataError),
        (
            b"<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'></feed>",
            ArXivIDNotFoundError,
        ),
        (
            b"<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom' "
            b"xmlns:arxiv='http://arxiv.org/schemas/atom'>"
            b"<entry><title>Sample</title></entry></feed>",
            ArXivCorruptedDataError,
        ),
    ],
)
@pytest.mark.django_db
def test_fetch_arxiv_metadata_query_errors(monkeypatch, xml_content, expected_exc):
    def fake_get(url, *args, **kwargs):
        return DummyResponse(xml_content, status_code=200, text=xml_content.decode(errors="ignore"))

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(expected_exc):
        fetch_arxiv_metadata("0000.0000v1")


@pytest.mark.django_db
def test_fetch_arxiv_metadata_urlerror(monkeypatch):
    def fake_get(url, *args, **kwargs):
        raise requests.exceptions.RequestException("network down")

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(ArXivConnectionError) as excinfo:
        fetch_arxiv_metadata("0000.0000v1")
    assert "Connection to arXiv could not be established" in str(excinfo.value)


@pytest.mark.django_db
def test_fetch_arxiv_metadata_file_download_failure(arxiv_fixtures, monkeypatch):
    metadata_resp = DummyResponse(arxiv_fixtures["xml"], status_code=200, text=arxiv_fixtures["xml"].decode())
    src_resp = DummyResponse(b"", status_code=403)
    mock_requests_get(
        monkeypatch,
        {
            "api/query": metadata_resp,
            "/src/": src_resp,
        },
    )

    __, errors = fetch_arxiv_metadata("0000.0000v1")

    assert "source_file" in errors
    assert errors["source_file"] == "HTTP 403"


@pytest.mark.django_db
def test_fetch_arxiv_metadata_connection_request_exception(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, *a, **k: (_ for _ in ()).throw(requests.exceptions.RequestException("network down")),
    )
    with pytest.raises(ArXivConnectionError) as excinfo:
        fetch_arxiv_metadata("0000.0000v1")
    assert "Connection to arXiv could not be established" in str(excinfo.value)


@pytest.mark.django_db
def test_fetch_arxiv_metadata_connection_http_error(monkeypatch):  # FIXME
    resp_404 = DummyResponse(b"", status_code=404)
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, *a, **k: resp_404,
    )

    with pytest.raises(ArXivConnectionError) as excinfo:
        fetch_arxiv_metadata("0000.0000v1")
    assert "Connection to arXiv could not be established" in str(excinfo.value)


@pytest.mark.django_db
def test_fetch_arxiv_metadata_doi_extraction(monkeypatch):
    doi_xml = (
        b"<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'>"
        b"<entry>"
        b"<id>http://arxiv.org/abs/0000.0000v1</id>"
        b"<title>Test</title>"
        b"<summary>Abstr</summary>"
        b"<arxiv:primary_category xmlns:arxiv='http://arxiv.org/schemas/atom' term='cs.AI'/>"
        b"<link title='doi' href='https://doi.org/10.1000/test'/></entry></feed>"
    )
    meta_resp = DummyResponse(doi_xml, status_code=200, text=doi_xml.decode())
    src_resp = DummyResponse(b"", status_code=403)
    mock_requests_get(monkeypatch, {"api/query": meta_resp, "/src/": src_resp})

    result, errors = fetch_arxiv_metadata("0000.0000v1")
    assert result["doi_link"] == "https://doi.org/10.1000/test"
    assert errors["source_file"] == "HTTP 403"


@pytest.mark.django_db
def test_fetch_arxiv_metadata_file_download_timeout(arxiv_fixtures, monkeypatch):
    metadata_resp = DummyResponse(arxiv_fixtures["xml"], status_code=200, text=arxiv_fixtures["xml"].decode())

    def fake_get(url, *args, **kwargs):
        if "api/query" in url:
            return metadata_resp
        raise requests.exceptions.Timeout("Request timed out")

    monkeypatch.setattr(requests, "get", fake_get)

    __, errors = fetch_arxiv_metadata("0000.0000")
    assert errors["source_file"] == "Request timed out"


@pytest.mark.django_db
def test_fetch_arxiv_metadata_unexpected_metadata_exception(monkeypatch):
    def fake_get(url, *args, **kwargs):
        raise RuntimeError("unexpected parsing failure")

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(GenericArxivError):
        fetch_arxiv_metadata("9999.9999v1")


@pytest.mark.django_db
def test_fetch_arxiv_metadata_unexpected_download_exception(monkeypatch, arxiv_fixtures):
    class CustomError(Exception):
        pass

    metadata_resp = DummyResponse(arxiv_fixtures["xml"], status_code=200, text=arxiv_fixtures["xml"].decode())

    def fake_get(url, *args, **kwargs):
        if "api/query" in url:
            return metadata_resp
        raise CustomError("unexpected download crash")

    monkeypatch.setattr(requests, "get", fake_get)

    __, errors = fetch_arxiv_metadata("9999.9999")
    assert errors["source_file"] == "unexpected download crash"


@pytest.mark.django_db
def test_article_creation_and_endpoint(rf, author, journal, arxiv_fixtures, monkeypatch):
    """
    Article is created from the data retrieved from the arxiv endpoint.

    Mock necessary external API requests, process the response, and check the integrity
    of the data and database records.

    :param rf: HttpRequest factory for creating request instances
    :param author: Test user instance representing the author of the article
    :param journal: Journal instance to associate with the article
    :param fixtures_data: Fixture data containing XML meta and source file content
    :param monkeypatch: Pytest monkeypatch fixture for modifying or mocking functions
    :return: None
    :raises AssertionError: If any of the assertions fail
    """
    xml_bytes = arxiv_fixtures["xml"]
    meta_resp = DummyResponse(content=xml_bytes, status_code=200, text=xml_bytes.decode("utf-8"))
    src_resp = DummyResponse(content=arxiv_fixtures["src"], status_code=200)

    mock_requests_get(
        monkeypatch,
        responses={
            "export.arxiv.org/api/query": meta_resp,
            "arxiv.org/src/": src_resp,
        },
    )

    request = make_arxiv_request(rf, author, journal, "1234.5678v1")
    response: HttpResponse = ArxivMicroservice.as_view()(request)

    assert response.status_code == 200

    data = json.loads(response.content.decode())
    assert data["status"] == "success"
    assert "article_id" in data
    assert 'Validated for "' in data["message"]

    article = Article.objects.get()

    assert article.title.strip() == "Notes on the double Wick rotated BTZ black hole"
    assert article.abstract.strip().startswith("We analyze the double Wick rotated BTZ")

    arxiv_id_obj = Identifier.objects.get(article=article, id_type="arxiv")
    assert arxiv_id_obj.identifier.endswith("v1")

    if "doi.org" in arxiv_fixtures["xml"].decode():
        doi_obj = Identifier.objects.get(article=article, id_type="doi")
        assert doi_obj.identifier.startswith("https://doi.org/")

    assert article.submission_data.arxiv_category == "hep-th"

    assert article.source_files.count() == 1
    saved = article.source_files.first().get_file(article, as_bytes=True)
    assert saved == arxiv_fixtures["src"]

    assert article.current_step == 0
    assert article.stage == STAGE_UNSUBMITTED
    assert article.owner == author
    assert article.correspondence_author == author
    assert author in article.authors.all()


@pytest.mark.django_db
def test_not_found_error_bubbles_up_via_empty_feed(rf, author, journal, arxiv_fixtures, monkeypatch):
    empty_meta = DummyResponse(
        content=arxiv_fixtures["xml_empty"],
        status_code=200,
        text=arxiv_fixtures["xml_empty"].decode(),
    )
    mock_requests_get(monkeypatch, {"export.arxiv.org/api/query": empty_meta})

    request = make_arxiv_request(rf, author, journal, "9999.99999")
    response: HttpResponse = ArxivMicroservice.as_view()(request)

    assert response.status_code == 500

    data = json.loads(response.content.decode())
    assert data["status"] == "error"


@pytest.mark.django_db
def test_already_used_error_bubbles_up_when_article_exists(rf, author, journal, arxiv_fixtures, monkeypatch):
    good_meta = DummyResponse(
        content=arxiv_fixtures["xml"],
        status_code=200,
        text=arxiv_fixtures["xml"].decode(),
    )
    good_src = DummyResponse(content=arxiv_fixtures["src"], status_code=200)
    mock_requests_get(
        monkeypatch,
        {
            "export.arxiv.org/api/query": good_meta,
            "arxiv.org/src/": good_src,
        },
    )
    req1 = make_arxiv_request(rf, author, journal, "1234.5678v1")
    ArxivMicroservice.as_view()(req1)
    assert Article.objects.count() == 1

    # Simulate the conclusion of the submission process
    article = Article.objects.first()
    article.current_step = 8
    article.stage = STAGE_UNASSIGNED
    article.save()

    mock_requests_get(
        monkeypatch,
        {
            "export.arxiv.org/api/query": good_meta,
        },
    )
    req2 = make_arxiv_request(rf, author, journal, "1234.5678v1")
    resp2: HttpResponse = ArxivMicroservice.as_view()(req2)
    body2 = resp2.content.decode()

    assert resp2.status_code == 500
    assert "already been submitted to the Journal" in body2


@pytest.mark.django_db
def test_connection_error_bubbles_up_on_requests_timeout(rf, author, journal, arxiv_fixtures, monkeypatch):
    def fail_get(url, *args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(requests, "get", fail_get)

    request = make_arxiv_request(rf, author, journal, "1234.5678v1")
    response: HttpResponse = ArxivMicroservice.as_view()(request)

    assert response.status_code == 500

    data = json.loads(response.content.decode())
    assert data["status"] == "error"
    assert "connection to arxiv could not be established" in data["message"].lower()


@pytest.mark.django_db
def test_blank_arxiv_id_still_invokes_fetch_and_import(rf, author, journal, arxiv_fixtures, monkeypatch):
    empty_meta = DummyResponse(
        content=arxiv_fixtures["xml_empty"],
        status_code=200,
        text=arxiv_fixtures["xml_empty"].decode(),
    )
    mock_requests_get(monkeypatch, {"export.arxiv.org/api/query": empty_meta})

    request = make_arxiv_request(rf, author, journal, "")
    response: HttpResponse = ArxivMicroservice.as_view()(request)
    body = response.content.decode()

    assert response.status_code == 500
    assert "cannot be found on arxiv.org" in body
