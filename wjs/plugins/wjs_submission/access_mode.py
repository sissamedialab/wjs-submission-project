from typing import NamedTuple

from core.models import Account
from django.utils.module_loading import import_string
from submission.models import Article, Licence

from .models import AccessMode
from .settings import ACCESS_MODE_CONTROL_FUNCTION, ACCESS_MODE_COUNTRIES, OA_CODE


class AccessModeConfiguration(NamedTuple):
    access_mode: AccessMode | None
    license: Licence | None
    copyright_text: str
    is_default: bool


def get_access_mode_configuration(user: Account, article: Article) -> AccessModeConfiguration:
    control_function_name = ACCESS_MODE_CONTROL_FUNCTION.get(article.journal.code, ACCESS_MODE_CONTROL_FUNCTION[None])
    control_function = import_string(control_function_name)
    return control_function(user, article)


def noop(user: Account, article: Article) -> AccessModeConfiguration:
    return AccessModeConfiguration(
        access_mode=None,
        license=None,
        copyright_text="",
        is_default=True,
    )


def get_oa_transformative_agreement(user: Account, article: Article):
    oa = AccessMode.objects.get(code=OA_CODE)
    countries = ACCESS_MODE_COUNTRIES.get(article.journal.code, ACCESS_MODE_COUNTRIES[None])
    if article.submission_data.affiliation_country.code in countries:
        journal_parameters = oa.parameters.get(journal=article.journal)
        return AccessModeConfiguration(
            access_mode=oa,
            license=journal_parameters.licence,
            copyright_text=journal_parameters.copyright,
            is_default=False,
        )
    return AccessModeConfiguration(
        access_mode=None,
        license=None,
        copyright_text="",
        is_default=True,
    )
