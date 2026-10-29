"""The step 8 summary shows the access mode, licence and rights that will actually apply."""

from collections.abc import Callable

import pytest
from plugins.wjs_submission.access_mode import get_effective_access_settings
from plugins.wjs_submission.models import AccessMode, RevisionStorage
from plugins.wjs_submission.settings import OA_CODE
from submission.models import Article, Licence


@pytest.fixture
def stored(article: Article) -> tuple[Article, AccessMode, Licence]:
    """Article with a stored access mode and a custom licence and rights, not synced with the presets."""
    access_mode = AccessMode.objects.exclude(code=OA_CODE).first()
    licence = Licence.objects.create(short_name="original", name="Original", journal=article.journal)
    article.submission_data.access_mode = access_mode
    article.submission_data.license_override = True
    article.submission_data.rights_override = True
    article.submission_data.save()
    article.license = licence
    article.rights = "original rights"
    article.save()
    return article, access_mode, licence


@pytest.mark.django_db
def test_effective_settings_plain_article(stored, install_plugins: Callable):
    """Without a revision the values stored on the article are shown."""
    article, access_mode, licence = stored
    assert get_effective_access_settings(article) == (access_mode, licence, "original rights")


@pytest.mark.django_db
def test_effective_settings_revision_same_access_mode(stored, install_plugins: Callable):
    """A revision that keeps the access mode shows the values stored on the article."""
    article, access_mode, licence = stored
    RevisionStorage.objects.create(
        article=article,
        revision_flow_type=RevisionStorage.RevisionFlowType.FULL,
        data={"access_mode": access_mode.pk},
    )
    assert get_effective_access_settings(article) == (access_mode, licence, "original rights")


@pytest.mark.parametrize(
    "flow_type", [RevisionStorage.RevisionFlowType.FULL, RevisionStorage.RevisionFlowType.METADATA]
)
@pytest.mark.django_db
def test_effective_settings_revision_changed_access_mode_shows_presets(
    stored, install_plugins: Callable, flow_type: str
):
    """
    A revision that selects another access mode shows its presets, the overrides do not apply to the new mode.

    ``PopulateRevisionStep7`` clears the override flags when the revision changes the access mode.
    """
    article, __, __ = stored
    new = AccessMode.objects.get(code=OA_CODE)
    preset = new.parameters.get(journal=article.journal)
    RevisionStorage.objects.create(article=article, revision_flow_type=flow_type, data={"access_mode": new.pk})
    assert get_effective_access_settings(article) == (new, preset.licence, preset.copyright)


@pytest.mark.django_db
def test_effective_settings_without_license_and_rights(stored, install_plugins: Callable):
    """An article without licence and rights does not break the summary."""
    article, access_mode, __ = stored
    article.license = None
    article.rights = None
    article.save()
    assert get_effective_access_settings(article) == (access_mode, None, "")
