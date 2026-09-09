"""
Django management command to import collaborations from the editorial "tabellone" JSON file.

Usage:
    python manage.py import_collaborations_json path/to/tabellone.json
"""

import json
import textwrap
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from ...helpers.collaborations import UNMAPPED_TABELLONE_KEYS, FieldComparison, ImportCollaboration

#: Width of the value columns of the comparison table.
VALUE_WIDTH = 45

#: How an empty value is rendered in the comparison table.
EMPTY_VALUE = "(empty)"


@dataclass
class Decision:
    """What the operator decided to do with a collaboration already in the database."""

    has_changes: bool = False
    needs_publishing: bool = False
    overwrite: bool = False
    publish: bool = False
    overwrite_all: bool = False
    publish_all: bool = False
    stop: bool = False

    @property
    def nothing_to_do(self) -> bool:
        """
        Tell whether the collaboration already matches the file and needs no decision at all.

        :return: True if the record has nothing to change.
        :rtype: bool
        """
        return not self.has_changes and not self.needs_publishing

    @property
    def changes_something(self) -> bool:
        """
        Tell whether the decision writes anything to the database.

        :return: True if the collaboration must be overwritten or approved for public listing.
        :rtype: bool
        """
        return self.overwrite or self.publish


class Command(BaseCommand):
    """
    Import the collaborations of a "tabellone" JSON file into the `Collaboration` table.

    Records are matched with the existing collaborations by the file's `full_name`
    (`Collaboration.name`). New collaborations are created and approved for public listing;
    collaborations already in the database are overwritten only after the operator has confirmed the
    differences shown as a table, and their public listing flag is set only if the operator asks for it.

    :ivar help: Description of the command's functionality displayed in the help text.
    :type help: str
    """

    help = "Import collaborations from a tabellone JSON file, asking confirmation before changing existing ones"

    def add_arguments(self, parser):  # noqa: PLR6301
        """
        Add command-line arguments to the parser for importing collaborations.

        :param parser: ArgumentParser instance to which arguments will be added.
        :type parser: argparse.ArgumentParser
        """
        parser.add_argument(
            "json_file",
            nargs="?",
            default="tabellone.json",
            type=str,
            help='Path to the JSON file containing the collaborations (default: "tabellone.json")',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run in dry-run mode (no database changes)",
        )
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            dest="noinput",
            help=(
                "Do not ask for confirmation: overwrite every collaboration that differs from the file "
                "and approve for public listing every collaboration listed in it"
            ),
        )

    def handle(self, *args, **options):
        """
        Import every collaboration of the JSON file, asking confirmation before each overwrite.

        :param args: Positional arguments passed to the command (not used in this implementation).
        :param options: Dictionary of command-line options, including:
            - "json_file" (str): Path to the JSON file containing the collaborations.
            - "dry_run" (bool, optional): If True, no changes are persisted. Defaults to False.
            - "noinput" (bool, optional): If True, existing collaborations are overwritten and approved
              for public listing without asking the operator. Defaults to False.
        :raises CommandError: If the file does not exist, cannot be read or does not contain collaborations.
        """
        dry_run = options["dry_run"]
        overwrite_all = publish_all = options["noinput"]
        records = self._load(options["json_file"])

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY-RUN mode - no changes will be made"))
        if UNMAPPED_TABELLONE_KEYS:
            skipped_keys = ", ".join(UNMAPPED_TABELLONE_KEYS)
            self.stdout.write(self.style.WARNING(f"Not imported (no counterpart in the database): {skipped_keys}"))

        counters = {"created": 0, "updated": 0, "published": 0, "unchanged": 0, "skipped": 0, "invalid": 0}
        for record in records:
            importer = ImportCollaboration(data=record, dry_run=dry_run)
            try:
                importer.validate()
                existing = importer.get_existing()
            except ValidationError as e:
                counters["invalid"] += 1
                self.stderr.write(self.style.ERROR(f'Skipping "{importer.name}": {"; ".join(e.messages)}'))
                continue

            if existing:
                decision = self._decide(importer, overwrite_all=overwrite_all, publish_all=publish_all)
                overwrite_all, publish_all = decision.overwrite_all, decision.publish_all
                if decision.stop:
                    self._interrupted()
                    break
                if decision.nothing_to_do:
                    counters["unchanged"] += 1
                    continue
                if not decision.changes_something:
                    counters["skipped"] += 1
                    self.stdout.write(f'"{importer.name}" left unchanged')
                    continue
            else:
                decision = Decision(overwrite=True, publish=True)

            __, created = importer.run(overwrite=decision.overwrite, publish=decision.publish)
            if created:
                counters["created"] += 1
            else:
                if decision.overwrite:
                    counters["updated"] += 1
                if decision.publish:
                    counters["published"] += 1
            done = self._describe(created=created, overwritten=decision.overwrite, published=decision.publish)
            self.stdout.write(f'"{importer.name}" {done}')

        self._report(counters, dry_run=dry_run)

    def _load(self, json_file: str) -> list[dict]:
        """
        Read the collaborations from the JSON file.

        Both the full "tabellone" structure (a `collaborations` list under a `version` key) and a bare
        list of collaboration records are accepted.

        :param json_file: Path to the JSON file containing the collaborations.
        :type json_file: str
        :raises CommandError: If the file does not exist, cannot be read or does not contain collaborations.
        :return: The collaboration records found in the file.
        :rtype: list[dict]
        """
        path = Path(json_file)
        if not path.exists():
            msg = f'File "{json_file}" does not exist'
            raise CommandError(msg)
        try:
            with path.open() as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON file: {e}"
            raise CommandError(msg) from e
        except OSError as e:
            msg = f"Error reading file: {e}"
            raise CommandError(msg) from e

        if isinstance(data, dict):
            version = data.get("version")
            if version:
                self.stdout.write(f"{path.name} version {version}")
            records = data.get("collaborations")
        else:
            records = data
        if not isinstance(records, list) or not records:
            msg = f'No collaborations found in "{json_file}"'
            raise CommandError(msg)
        self.stdout.write(f"{len(records)} collaborations found in {path.name}")
        return records

    def _decide(self, importer: ImportCollaboration, *, overwrite_all: bool, publish_all: bool) -> "Decision":
        """
        Work out what to do with a collaboration that is already in the database, asking the operator.

        The two questions are independent: the operator can refuse to overwrite the values but still
        approve the collaboration for public listing, and the other way around.

        :param importer: The importer of the record being processed.
        :type importer: ImportCollaboration
        :param overwrite_all: Whether the operator already agreed to overwrite every collaboration.
        :type overwrite_all: bool
        :param publish_all: Whether the operator already agreed to approve every collaboration.
        :type publish_all: bool
        :return: What has to be done, and what the operator agreed to do for the next records.
        :rtype: Decision
        """
        decision = Decision(overwrite_all=overwrite_all, publish_all=publish_all)
        decision.has_changes = importer.has_changes()
        decision.needs_publishing = importer.needs_publishing()
        if decision.nothing_to_do:
            return decision

        if decision.has_changes:
            answer = "all" if overwrite_all else self._ask_overwrite(importer)
            decision.stop = answer == "quit"
            decision.overwrite = answer in ("yes", "all")
            decision.overwrite_all = overwrite_all or answer == "all"
        if decision.needs_publishing and not decision.stop:
            answer = "all" if publish_all else self._ask_publish(importer)
            decision.stop = answer == "quit"
            decision.publish = answer in ("yes", "all")
            decision.publish_all = publish_all or answer == "all"
        return decision

    def _ask_overwrite(self, importer: ImportCollaboration) -> str:
        """
        Show the differences between the database and the file and ask the operator whether to overwrite them.

        :param importer: The importer of the record being processed.
        :type importer: ImportCollaboration
        :return: The operator's choice: "yes", "no", "all" or "quit".
        :rtype: str
        """
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f'"{importer.name}" already exists with different values:'))
        self.stdout.write(self._render_table(importer.compare()))
        return self._prompt("Overwrite the database with the values from the file?")

    def _ask_publish(self, importer: ImportCollaboration) -> str:
        """
        Ask the operator whether to approve for public listing a collaboration that is not approved yet.

        :param importer: The importer of the record being processed.
        :type importer: ImportCollaboration
        :return: The operator's choice: "yes", "no", "all" or "quit".
        :rtype: str
        """
        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f'"{importer.name}" is in the file but is not approved for public listing '
                f"(public_listing is false in the database)."
            )
        )
        return self._prompt("Approve it for public listing?")

    def _prompt(self, question: str) -> str:
        """
        Ask the operator a yes/no question, until a valid answer is given.

        An empty answer means "no", so that pressing enter never changes the database; the end of the
        input stream means "quit", so that the import stops instead of looping.

        :param question: The question to ask the operator.
        :type question: str
        :return: The operator's choice: "yes", "no", "all" or "quit".
        :rtype: str
        """
        answers = {"y": "yes", "yes": "yes", "n": "no", "no": "no", "a": "all", "all": "all", "q": "quit", "": "no"}
        prompt = f"{question} [y]es / [N]o / [a]ll / [q]uit: "
        while True:
            try:
                answer = input(prompt).strip().lower()
            except EOFError:
                self.stdout.write("")
                return "quit"
            if answer in answers:
                return answers[answer]
            self.stdout.write(self.style.ERROR(f'"{answer}" is not a valid answer'))

    def _interrupted(self) -> None:
        """Tell the operator that the import stops here."""
        self.stdout.write(self.style.WARNING("Import interrupted by the operator"))

    @staticmethod
    def _describe(*, created: bool, overwritten: bool, published: bool) -> str:
        """
        Describe what has been done to a collaboration.

        :param created: Whether the collaboration has been created.
        :type created: bool
        :param overwritten: Whether the collaboration's values have been replaced by the file's ones.
        :type overwritten: bool
        :param published: Whether the collaboration's public listing flag has been set.
        :type published: bool
        :return: The description, to be appended to the collaboration name.
        :rtype: str
        """
        if created:
            return "created and approved for public listing"
        done = (["overwritten"] if overwritten else []) + (["approved for public listing"] if published else [])
        return " and ".join(done)

    @staticmethod
    def _render_table(comparisons: list[FieldComparison]) -> str:
        """
        Render the comparison of every field as a textual table.

        Changed fields are marked with an asterisk; values wider than the column are wrapped.

        :param comparisons: The field-by-field comparison of the record with the database.
        :type comparisons: list[FieldComparison]
        :return: The table, ready to be written to the output.
        :rtype: str
        """
        label_width = max([len(comparison.tabellone_key) for comparison in comparisons] + [len("field")]) + 2
        separator = f"{'-' * label_width}-+-{'-' * VALUE_WIDTH}-+-{'-' * VALUE_WIDTH}"
        lines = [
            f"{'field'.ljust(label_width)} | {'database'.ljust(VALUE_WIDTH)} | {'file'.ljust(VALUE_WIDTH)}",
            separator,
        ]
        for comparison in comparisons:
            label = f"{'*' if comparison.changed else ' '} {comparison.tabellone_key}"
            cells = (
                textwrap.wrap(Command._display(comparison.db_value), VALUE_WIDTH) or [""],
                textwrap.wrap(Command._display(comparison.file_value), VALUE_WIDTH) or [""],
            )
            for row, (db_line, file_line) in enumerate(zip_longest(*cells, fillvalue="")):
                first_column = (label if row == 0 else "").ljust(label_width)
                lines.append(f"{first_column} | {db_line.ljust(VALUE_WIDTH)} | {file_line.ljust(VALUE_WIDTH)}")
        return "\n".join(lines)

    @staticmethod
    def _display(value: str | bool) -> str:
        """
        Render a field value for the comparison table.

        :param value: The value read from the database or from the file.
        :type value: str | bool
        :return: The value as it must appear in the table.
        :rtype: str
        """
        if isinstance(value, bool):
            return "true" if value else "false"
        return value or EMPTY_VALUE

    def _report(self, counters: dict[str, int], *, dry_run: bool) -> None:
        """
        Write the summary of the import.

        :param counters: How many collaborations have been created, overwritten, approved for public listing,
            left unchanged or skipped.
        :type counters: dict[str, int]
        :param dry_run: Whether the import has been run in dry-run mode.
        :type dry_run: bool
        """
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("Import summary:"))
        self.stdout.write(f"Collaborations created: {counters['created']}")
        self.stdout.write(f"Collaborations overwritten: {counters['updated']}")
        self.stdout.write(f"Collaborations approved for public listing: {counters['published']}")
        self.stdout.write(f"Collaborations already up to date: {counters['unchanged']}")
        self.stdout.write(f"Collaborations left unchanged by the operator: {counters['skipped']}")
        if counters["invalid"]:
            self.stdout.write(self.style.ERROR(f"Records with invalid values: {counters['invalid']}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY-RUN completed - nothing has been written to the database"))
        else:
            self.stdout.write(self.style.SUCCESS("\nImport completed successfully!"))
