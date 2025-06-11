import pytest
from django.contrib.auth import get_user_model

Account = get_user_model()


@pytest.fixture
def admin() -> Account:
    """Create admin user."""
    admin, _ = Account.objects.get_or_create(
        username="admin@invalid.com",
        email="admin@invalid.com",
        first_name="Admin",
        last_name="Admin",
        is_active=True,
        is_staff=True,
        is_admin=True,
        is_superuser=True,
    )
    return admin
