import requests


class DummyResponse:
    """Dummy response class for testing."""

    def __init__(self, content: bytes, status_code: int = 200, text: str | None = None):
        """Initialize with content, status code and optional text."""
        self.content = content
        self.status_code = status_code
        self.text = text if text is not None else content.decode(errors="ignore")

    def raise_for_status(self):
        """
        Raise an HTTPError if the HTTP response status code indicates an error.

        This method checks if the status code of an HTTP response falls outside the
        successful range (200-299) and raises an HTTPError exception if it does.

        :raises requests.exceptions.HTTPError: If the status code is not between 200 and 299.
        """
        if not (200 <= self.status_code < 300):
            raise requests.exceptions.HTTPError(self.status_code)


def mock_requests_get(monkeypatch, responses: dict | None = None):
    """Mock requests.get for metadata and file downloads without raising on metadata."""

    def fake_get(url, *args, **kwargs):
        for pattern, response in (responses or {}).items():
            if pattern in url:
                return response
        return DummyResponse(b"", 404)

    monkeypatch.setattr(requests, "get", fake_get)


def make_arxiv_request(rf, user, journal, arxiv_id):
    """
    Build a POST request with arxiv_id and attach user/journal.
    """
    req = rf.post("/fake-url/", data={"arxiv_id": arxiv_id})
    req.user = user
    req.journal = journal
    return req
