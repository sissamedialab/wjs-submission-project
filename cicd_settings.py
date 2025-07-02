"""
CI/CD settings to run management commands in CI/CD.

Management commands are run using a "normal" janeway setup, setting JANEWAY_SETTINGS_MODULE, with plugins installed
the janeway way etc because we have control over the initialisation of the test project.
"""

from wjs.defaults.settings_submission import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "janeway",
        "USER": "janeway",
        "PASSWORD": "janeway",
        "HOST": "db",
        "PORT": "5432",
    },
}
