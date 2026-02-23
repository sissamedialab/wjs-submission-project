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
