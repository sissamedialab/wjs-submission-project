from django.db import migrations


class Migration(migrations.Migration):
    # Split from 0026 on purpose: PostgreSQL raised "cannot ALTER TABLE
    # wjs_submission_articlesubmission because it has pending trigger events" when the
    # RunPython data copy and these RemoveField operations ran in the same atomic migration
    # (DEV deploy of !191, 2026-11-13). Running the data copy and the column drop as separate
    # migrations/transactions lets the pending trigger events from the UPDATEs in 0026 clear
    # before the ALTER TABLE here.
    dependencies = [
        ("wjs_submission", "0026_merge_cas_das_url_into_text"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="articlesubmission",
            name="cas_url",
        ),
        migrations.RemoveField(
            model_name="articlesubmission",
            name="das_url",
        ),
    ]
