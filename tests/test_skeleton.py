import pytest
from django.contrib.auth import get_user_model
from django.test.client import Client
from django.urls import reverse

Account = get_user_model()


@pytest.mark.django_db
def test_me(client: Client, admin: Account):
    url = reverse("wjs_submission_manager")
    response = client.get(url)
    assert response.status_code == 302  # noqa: PLR2004
    # response.headers.get('Location') is the homepage... why?

    client.force_login(admin)
    response = client.get(url)
    assert response.status_code == 200  # noqa: PLR2004
