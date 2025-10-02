"""Default WJS submission settings."""  # noqa: INP001

import os
from pathlib import Path

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

DEBUG = True

# Plugins is installed by Janeway, not Django!
# No: INSTALLED_APPS = ["wjs_submission",]  # noqa: ERA001
INSTALLED_APPS = [
    "django_bootstrap5",
    "wjs.themes",
]

# This is the default redirect if no other sites are found.
DEFAULT_HOST = "https://www.example.org"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "default@default.it"

LOGIN_REDIRECT_URL = reverse_lazy("core_edit_profile")
LOGIN_URL = reverse_lazy("core_login")

# CATCHA_TYPE should be either 'simple_math', 'recaptcha' or 'hcaptcha' to enable captcha
# fields, otherwise disabled
CAPTCHA_TYPE = "simple_math"

# If using recaptcha complete the following
RECAPTCHA_PRIVATE_KEY = ""
RECAPTCHA_PUBLIC_KEY = ""

# If using hcaptcha complete the following:
HCAPTCHA_SITEKEY = ""
HCAPTCHA_SECRET = ""

# ORCID Settings
ENABLE_ORCID = False
ORCID_API_URL = "http://pub.orcid.org/v1.2_rc7/"
ORCID_URL = "https://orcid.org/oauth/authorize"
ORCID_TOKEN_URL = "https://pub.orcid.org/oauth/token"  # noqa: S105
ORCID_CLIENT_SECRET = ""
ORCID_CLIENT_ID = ""

# Default Langague
LANGUAGE_CODE = "en"


def ugettext(s: str) -> str:
    """Let Django statically translate the verbose names of the languages using the standard i18n solution."""
    return s


LANGUAGES = (
    ("en", ugettext("English")),
    ("en-us", ugettext("English (US)")),
    ("fr", ugettext("French")),
    ("de", ugettext("German")),
    ("nl", ugettext("Dutch")),
    ("cy", ugettext("Welsh")),
    ("es", ugettext("Spanish")),
    ("pt", ugettext("Portughese")),
)

MODELTRANSLATION_DEFAULT_LANGUAGE = "en"
MODELTRANSLATION_PREPOPULATE_LANGUAGE = "en"

MODELTRANSLATION_FALLBACK_LANGUAGES = {
    "default": ("en", "es", "pt"),
    "es": ("pt", "en"),
    "pt": ("es", "en"),
}


URL_CONFIG = "domain"  # path or domain

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "janeway",
        "USER": "postgres",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    },
}

# OIDC Settings
ENABLE_OIDC = False
OIDC_SERVICE_NAME = "OIDC Service Name"
OIDC_RP_CLIENT_ID = ""
OIDC_RP_CLIENT_SECRET = ""
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_OP_AUTHORIZATION_ENDPOINT = ""
OIDC_OP_TOKEN_ENDPOINT = ""
OIDC_OP_USER_ENDPOINT = ""
OIDC_OP_JWKS_ENDPOINT = ""


TIME_ZONE = "Europe/Rome"

ENABLE_FULL_TEXT_SEARCH = True
CORE_FILETEXT_MODEL = "core.PGFileText"

REDIS_CACHE_URL = os.environ.get("REDIS_CACHE_URL", "redis://localhost:6379/1")
REDIS_QCLUSTER_URL = os.environ.get("REDIS_QCLUSTER_URL", "redis://localhost:6379/10")

Q_CLUSTER = {
    "name": "wjs-janeway",
    "label": "Task WJS",
    "workers": 1,
    "sync": True,
    "redis": REDIS_QCLUSTER_URL,
    "retry": 90,
    "timeout": 60,
}


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}

LOCALE_PATHS = [Path(__file__).parents[1] / "locale"]

JCOMASSISTANT_URL = "http://janeway-services.ud.sissamedialab.it:1234/jcomassistant/"
YAKUNIN_URL = "http://janeway-services.ud.sissamedialab.it:1235/watermark/"


# Override the default bootstrap5 css as we customize it, and the css below will include all the bootstrap5 css plus
# our own customizations
# We might have an issue if we want to customize this per journal, but I would leave as an issue as it has a low impact
# for now as it's just the dashboard css
BOOTSTRAP5 = {"css_url": "/static/JCOM-theme/css/wjs_review.css"}


SUBMISSION_ARTICLE_LANGUAGES = {
    None: [("eng", _("English"))],
    "JCOM": [
        (
            "eng",
            _("English"),
        ),
        ("deu", _("German")),
        ("fra", _("French")),
        ("spa", _("Spanish")),
        ("por", _("Portuguese")),
        ("ita", _("Italian")),
    ],
    "JCOMAL": [("spa", _("Spanish")), ("por", _("Portuguese"))],
}
