from django.db import migrations

OLD_LABEL = "Author(s) take full responsibility for any use of Artificial Intelligence made in preparing this paper"
NEW_LABEL = "Artificial Intelligence"


def rename_use_of_ai_field(apps, schema_editor):
    """Rename the "Use of AI" submission fields; existing FieldAnswer rows follow through the foreign key."""
    Field = apps.get_model("submission", "Field")
    Field.objects.filter(name=OLD_LABEL).update(name=NEW_LABEL)


def restore_use_of_ai_field(apps, schema_editor):
    Field = apps.get_model("submission", "Field")
    Field.objects.filter(name=NEW_LABEL).update(name=OLD_LABEL)


class Migration(migrations.Migration):
    dependencies = [
        ("wjs_submission", "0023_remove_articlesubmission_special_request_updated_and_more"),
        ("submission", "0081_auto_20240927_1021"),
    ]

    operations = [migrations.RunPython(rename_use_of_ai_field, restore_use_of_ai_field)]
