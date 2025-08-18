"""
Django management command to import JHEP keywords from JSON file.

Usage:
    python manage.py import_jhep_keywords path/to/jhep-kwds.json
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...helpers.keywords import import_keywords_from_wjapp


class Command(BaseCommand):
    help = "Import JHEP keywords from JSON file and create KeywordGroup and Keyword instances"

    def add_arguments(self, parser):  # noqa: PLR6301
        """
        Add command-line arguments to the parser for importing JHEP keywords.

        :param parser: ArgumentParser instance to which arguments will be added.
        :type parser: argparse.ArgumentParser
        :raises ValueError: If any invalid argument is provided.
        """
        parser.add_argument("json_file", type=str, help="Path to the JSON file containing JHEP keywords")
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing keywords and groups before importing",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run in dry-run mode (no database changes)",
        )
        parser.add_argument("--journal", help="Journal to assign keywords to")

    def handle(self, *args, **options):
        """
        Handle the import of keywords from a JSON file for a specific journal.

        Provides options for clearing existing keywords, running in dry-run mode, and specifying
        a journal ID.

        :param args: Positional arguments passed to the command (not used in this implementation).
        :param options: Dictionary of command-line options, including:
            - "json_file" (str): Path to the JSON file containing keywords.
            - "clear" (bool, optional): Whether to clear existing keywords before importing. Defaults to False.
            - "dry_run" (bool, optional): If True, no changes will be persisted. Defaults to False.
            - "journal_id" (int, optional): The ID of the journal to which keywords are being imported.
                Defaults to False.
        :return: None
        :raises CommandError: If the JSON file does not exist, is invalid, or if an error occurs during file
            processing or import operation.
        """
        json_file = options["json_file"]
        clear_existing = options.get("clear", False)
        dry_run = options.get("dry_run", False)
        journal_code = options.get("journal", False)

        # Check if file exists
        if not Path(json_file).exists():
            msg = f'File "{json_file}" does not exist'
            raise CommandError(msg)

        # Load JSON data
        try:
            with Path(json_file).open() as f:  # noqa: PLW1514
                data = json.load(f)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON file: {e}"
            raise CommandError(msg) from e
        except Exception as e:
            msg = f"Error reading file: {e}"
            raise CommandError(msg) from e

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY-RUN mode - no changes will be made"))

        try:
            output = import_keywords_from_wjapp(journal_code, clear_existing, dry_run, data)
            # Print summary
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write(self.style.SUCCESS("Import Summary:"))
            self.stdout.write(f"Main groups created: {output['groups_created']}")
            self.stdout.write(f"Subgroups created: {output['subgroups_created']}")
            self.stdout.write(f"Keywords created: {output['keywords_created']}")
            self.stdout.write(f"Keywords skipped (already exist): {output['keywords_skipped']}")
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write("Database Statistics:")
            self.stdout.write(f"Total KeywordGroups in database: {output['total_groups']}")
            self.stdout.write(f"Total Keywords in database: {output['total_keywords']}")

            # Rollback if dry-run
            if dry_run:
                self.stdout.write(self.style.WARNING("\nDRY-RUN completed - all changes rolled back"))
            else:
                self.stdout.write(self.style.SUCCESS("\nImport completed successfully!"))
        except Exception as e:
            msg = f"Error during import: {e}"
            raise CommandError(msg) from e
