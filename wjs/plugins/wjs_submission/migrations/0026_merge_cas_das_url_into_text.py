from django.db import migrations
from django.db.models import F


def copy_url_into_text(apps, schema_editor):
    """Copy cas_url/das_url values into cas_text/das_text, on the model and on in-flight revisions."""
    ArticleSubmission = apps.get_model("wjs_submission", "ArticleSubmission")
    ArticleSubmission.objects.filter(cas="url").update(cas_text=F("cas_url"))
    ArticleSubmission.objects.filter(das="url").update(das_text=F("das_url"))

    RevisionStorage = apps.get_model("wjs_submission", "RevisionStorage")
    for revision in RevisionStorage.objects.all():
        data = revision.data
        changed = False
        if "cas_url" in data:
            if data.get("cas") == "url" and not data.get("cas_text"):
                data["cas_text"] = data["cas_url"]
            del data["cas_url"]
            changed = True
        if "das_url" in data:
            if data.get("das") == "url" and not data.get("das_text"):
                data["das_text"] = data["das_url"]
            del data["das_url"]
            changed = True
        if changed:
            revision.save(update_fields=["data"])


def restore_url_from_text(apps, schema_editor):
    """Restore cas_url/das_url from cas_text/das_text, for "url"-typed rows, on the model and on revisions."""
    ArticleSubmission = apps.get_model("wjs_submission", "ArticleSubmission")
    ArticleSubmission.objects.filter(cas="url").update(cas_url=F("cas_text"))
    ArticleSubmission.objects.filter(das="url").update(das_url=F("das_text"))

    RevisionStorage = apps.get_model("wjs_submission", "RevisionStorage")
    for revision in RevisionStorage.objects.all():
        data = revision.data
        changed = False
        if data.get("cas") == "url" and "cas_text" in data:
            data["cas_url"] = data["cas_text"]
            changed = True
        if data.get("das") == "url" and "das_text" in data:
            data["das_url"] = data["das_text"]
            changed = True
        if changed:
            revision.save(update_fields=["data"])


class Migration(migrations.Migration):
    dependencies = [
        ("wjs_submission", "0025_articlesubmission_cas_text_das_text_and_choices"),
    ]

    operations = [
        migrations.RunPython(copy_url_into_text, restore_url_from_text),
    ]
