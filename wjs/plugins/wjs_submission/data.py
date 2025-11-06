from django.utils.text import slugify


def create_access_mode(apps, schema_editor):
    AccessMode = apps.get_model("wjs_submission", "AccessMode")
    AccessModeJournal = apps.get_model("wjs_submission", "AccessModeJournal")
    Journal = apps.get_model("journal", "Journal")
    Licence = apps.get_model("submission", "Licence")
    for name in ("Open Access", "Not open access", "OA Transformative agreement"):
        mode, __ = AccessMode.objects.get_or_create(name=name, code=slugify(name))
        for journal in Journal.objects.all():
            licence = Licence.objects.get(short_name="CC BY-SA 4.0", journal=journal)
            AccessModeJournal.objects.get_or_create(
                access_mode=mode, journal=journal, copyright="Authors", licence=licence
            )
