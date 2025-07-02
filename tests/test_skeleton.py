from collections.abc import Callable

import pytest
from django.contrib.auth import get_user_model
from django.test.client import Client
from django.urls import reverse
from journal.models import Journal
from utils.plugins import check_plugin_exists

Account = get_user_model()


@pytest.mark.django_db
def test_me(
    journal: Journal,
    client: Client,
    admin: Account,
    install_plugins: Callable,  # noqa: ARG001
):
    assert check_plugin_exists("wjs_submission")
    url = reverse("wjs_submission_manager")
    assert journal.code in url
    response = client.get(url)
    assert response.status_code == 302  # noqa: PLR2004
    assert "login" in response.headers.get("Location")

    client.force_login(admin)
    response = client.get(url)
    assert response.status_code == 200  # noqa: PLR2004
