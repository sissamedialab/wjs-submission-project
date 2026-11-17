from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("wjs_submission", "0027_remove_cas_das_url"),
    ]

    operations = [
        UnaccentExtension(),
    ]
