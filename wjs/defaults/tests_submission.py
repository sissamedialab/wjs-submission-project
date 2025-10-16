"""
Merge janeway_global_settings and custom settings for pytest.

isort:skip_file
"""  # noqa: INP001

from collections.abc import Mapping
from copy import copy
from typing import Any

from core.janeway_global_settings import *  # noqa: F403
from django.db import connection

from .settings_submission import INSTALLED_APPS as SUBMISSION_APPS
from .settings_submission import SUBMISSION_ARTICLE_LANGUAGES  # noqa: F401

# CLone Janeway INSTALLED_APPS / MIDDLEWARE to merge with ones defined in wjs.default.settings which are imported below
JANEWAY_INSTALLED_APPS = copy(INSTALLED_APPS)  # noqa: F405
JANEWAY_MIDDLEWARE = copy(MIDDLEWARE)  # noqa: F405

try:
    # Non committed local settings may non exists (eg: in the CI)
    from core.settings import *  # noqa: F403

    # Merge Janeway, wjs defaults and submission INSTALLED_APPS preserving the order but removing the duplicates
    INSTALLED_APPS = list(dict.fromkeys(JANEWAY_INSTALLED_APPS + INSTALLED_APPS + SUBMISSION_APPS))  # noqa: F405
    # Merge Janeway, wjs defaults MIDDLEWARE
    MIDDLEWARE = JANEWAY_MIDDLEWARE + MIDDLEWARE  # noqa: F405
except ImportError:
    # Merge Janeway and submission INSTALLED_APPS preserving the order but removing the duplicates
    INSTALLED_APPS = list(dict.fromkeys(JANEWAY_INSTALLED_APPS + SUBMISSION_APPS))


# Check wjs-profile-project wjs.defaults files if you need to manage django apps or middleware.

CAPTCHA_TYPE = "🐖"

# Ported class from janeway to skip migrations.
# Data created by migrations must be recreated by fixtures in conftest
IN_TEST_RUNNER = True


class SkipMigrations(Mapping):
    """
    Ensure the install migrations run before syncing db.

    Django's migration executor will always pre_render database state from
    the models of unmigrated apps before running those declared in
    MIGRATION_MODULES. As a result, we can't run the install migrations
    first, while skipping the remaining migrations. Instead, we run
    the required SQL here.

    See also https://docs.djangoproject.com/en/5.2/ref/settings/#std-setting-MIGRATION_MODULES
    """

    def __getitem__(self, key: Any):
        if key == "install" and connection.vendor == "postgresql":
            cursor = connection.cursor()
            cursor.execute("CREATE EXTENSION IF NOT EXISTS citext;")

    def __contains__(self, key: Any):
        return True

    def __iter__(self):
        return iter("")

    def __len__(self):
        return 1


MIGRATION_MODULES = SkipMigrations()


JCOMASSISTANT_MOCK_FILE = ""

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
