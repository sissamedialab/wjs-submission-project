from typing import TypedDict

from django.utils.text import slugify

from .settings import OA_CERN_CODE, OA_CODE, OA_CODE_TA


def create_access_mode(apps, schema_editor):
    AccessMode = apps.get_model("wjs_submission", "AccessMode")
    AccessModeJournal = apps.get_model("wjs_submission", "AccessModeJournal")
    Journal = apps.get_model("journal", "Journal")
    Licence = apps.get_model("submission", "Licence")
    for code, name in {
        OA_CODE: "Open Access",
        slugify("Not open access"): "Not open access",
        OA_CODE_TA: "OA Transformative agreement",
        OA_CERN_CODE: "CERN OA",
    }.items():
        mode, __ = AccessMode.objects.get_or_create(name=name, code=code)
        for journal in Journal.objects.all():
            licence = Licence.objects.get(short_name="CC BY-SA 4.0", journal=journal)
            AccessModeJournal.objects.get_or_create(
                access_mode=mode, journal=journal, copyright="Authors", licence=licence
            )


class RevisionValidationData(TypedDict):
    """
    Represent validation data for a revision process.

    This class is a TypedDict, which ensures the presence and type of specific
    attributes used to track the status of various requirements in a submission
    revision process.

    :ivar valid: Indicates if the revision data is valid.
    :type valid: bool
    :ivar submission_requirements: Indicates if submission requirements are met.
    :type submission_requirements: bool
    :ivar cover_letter: Indicates if a cover letter is included and valid.
    :type cover_letter: bool
    :ivar revision_files: Indicates if all required revision files are provided.
    :type revision_files: bool
    """

    valid: bool
    submission_requirements: bool
    cover_letter: bool
    revision_files: bool
