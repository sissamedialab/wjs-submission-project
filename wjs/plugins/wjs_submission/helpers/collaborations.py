"""Import of the collaborations "tabellone" (the editorial spreadsheet exported as `tabellone.json`)."""

import difflib
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Collaboration

#: Mapping between the keys of a `tabellone.json` collaboration record and the `Collaboration` fields.
TABELLONE_FIELDS: dict[str, str] = {
    "full_name": "name",
    "short_name": "short_name",
    "email": "institutional_email",
    "logo": "logo_name",
    "logoSize": "logo_size",
    "moretex": "moretex",
    "authorList": "author_list_mode",
    "collaborationList": "collaboration_list_mode",
    "cluster": "cluster",
    "sample_papers": "sample_papers",
    "notes": "notes",
}

#: Keys of a `tabellone.json` record that have no counterpart in `Collaboration` and are therefore not imported.
#: Note that `logo` is imported into `Collaboration.logo_name` as-is: it is the base name of an image file,
#: while `Collaboration.logo` is a reference to a `core.File` that must be uploaded and linked separately.
UNMAPPED_TABELLONE_KEYS: tuple[str, ...] = ()

#: Field name used to match a record in `tabellone.json` with a `Collaboration` already in the database.
MATCH_KEY = "full_name"

#: How similar an invalid value must be to an allowed one to be suggested as the intended value
#: (see :py:func:`difflib.get_close_matches`).
SUGGESTION_CUTOFF = 0.6

#: Choices allowed for the fields that carry a LaTeX command mode.
ALLOWED_MODES: dict[str, list[str]] = {
    "author_list_mode": Collaboration.AuthorListMode.values,
    "collaboration_list_mode": Collaboration.CollaborationListMode.values,
}


@dataclass
class FieldComparison:
    """The database value and the file value of a single field of a collaboration."""

    field_name: str
    tabellone_key: str
    db_value: str
    file_value: str
    changed: bool


@dataclass
class ImportCollaboration:
    """
    Import a single collaboration record of `tabellone.json` into a `Collaboration`.

    The record is matched with an existing collaboration by `tabellone.json`'s `full_name`
    (`Collaboration.name`); the matching collaboration, if any, is overwritten with the record's values.
    Since overwriting discards data possibly edited in Janeway, the caller is expected to inspect
    :py:meth:`compare` and to confirm the operation before calling :py:meth:`run`.

    Collaborations created by the import are approved for public listing, because the file is the
    editorial list of the known collaborations. The flag of a collaboration already in the database
    is left alone unless :py:meth:`run` is explicitly told to set it (see :py:meth:`needs_publishing`).
    """

    data: dict
    dry_run: bool = False
    _instance: Collaboration | None = field(default=None, init=False, repr=False)

    @property
    def name(self) -> str:
        """
        Return the name used to match this record with a collaboration in the database.

        :return: The record's full name, without surrounding spaces.
        :rtype: str
        """
        return str(self.data.get(MATCH_KEY) or "").strip()

    def get_values(self) -> dict[str, str | bool]:
        """
        Extract from the record the values of the `Collaboration` fields this importer writes.

        Keys missing from the record are left out, so that a partial record does not blank out
        the corresponding database values.

        :return: A mapping of `Collaboration` field name to the value read from the record.
        :rtype: dict[str, str | bool]
        """
        values = {}
        for tabellone_key, field_name in TABELLONE_FIELDS.items():
            if tabellone_key not in self.data:
                continue
            value = self.data[tabellone_key]
            values[field_name] = value if isinstance(value, bool) else str(value or "").strip()
        return values

    def get_existing(self, *, lock: bool = False) -> Collaboration | None:
        """
        Retrieve the collaboration matching this record, if it is already in the database.

        :param lock: Whether to lock the matching row for the current transaction.
        :type lock: bool
        :raises ValidationError: If more than one collaboration matches the record's name.
        :return: The matching collaboration, or None if the record is new.
        :rtype: Collaboration | None
        """
        if self._instance is None:
            queryset = Collaboration.objects.select_for_update() if lock else Collaboration.objects.all()
            matches = list(queryset.by_name(self.name))
            if len(matches) > 1:
                msg = f'{len(matches)} collaborations are named "{self.name}": fix the duplicates and import again'
                raise ValidationError(msg)
            self._instance = matches[0] if matches else None
        return self._instance

    def compare(self, instance: Collaboration | None = None) -> list[FieldComparison]:
        """
        Compare the record with the database, field by field.

        :param instance: The collaboration to compare the record with. Defaults to the matching one.
        :type instance: Collaboration | None
        :return: One comparison per imported field, in the order they appear in `tabellone.json`.
        :rtype: list[FieldComparison]
        """
        if instance is None:
            instance = self.get_existing()
        values = self.get_values()
        comparisons = []
        for tabellone_key, field_name in TABELLONE_FIELDS.items():
            if field_name not in values:
                continue
            db_value = getattr(instance, field_name) if instance else ""
            file_value = values[field_name]
            comparisons.append(
                FieldComparison(
                    field_name=field_name,
                    tabellone_key=tabellone_key,
                    db_value=db_value,
                    file_value=file_value,
                    changed=bool(instance) and db_value != file_value,
                )
            )
        return comparisons

    def has_changes(self) -> bool:
        """
        Tell whether importing this record would change the matching collaboration.

        :return: True if the record differs from the database or is not in it yet.
        :rtype: bool
        """
        if not self.get_existing():
            return True
        return any(comparison.changed for comparison in self.compare())

    def needs_publishing(self) -> bool:
        """
        Tell whether the matching collaboration is in the database but not approved for public listing.

        A collaboration listed in the file is meant to be selectable during submission, so a cleared
        flag is a difference the operator has to decide about, even when every other field matches.

        :return: True if the matching collaboration has the public listing flag cleared.
        :rtype: bool
        """
        instance = self.get_existing()
        return bool(instance) and not instance.public_listing

    def validate(self) -> None:
        """
        Check that the record can be imported.

        :raises ValidationError: If the record has no name or carries a value not allowed by the model choices.
        """
        if not self.name:
            msg = f'Record has no "{MATCH_KEY}": {self.data}'
            raise ValidationError(msg)
        values = self.get_values()
        errors = [
            self._invalid_value_message(field_name, values[field_name], allowed)
            for field_name, allowed in ALLOWED_MODES.items()
            if values.get(field_name) and values[field_name] not in allowed
        ]
        if errors:
            raise ValidationError(errors)

    @staticmethod
    def _invalid_value_message(field_name: str, value: str, allowed: list[str]) -> str:
        """
        Describe a value not allowed by the model choices.

        A typo or a difference in case is far more common than a value from another vocabulary, so the
        closest allowed value is suggested when there is one; the full list is shown only otherwise, to
        keep the message short.

        :param field_name: The `Collaboration` field the value has been read for.
        :type field_name: str
        :param value: The value read from the record.
        :type value: str
        :param allowed: The values allowed by the model choices.
        :type allowed: list[str]
        :return: The error message to be collected by :py:meth:`validate`.
        :rtype: str
        """
        candidates = {choice.casefold(): choice for choice in allowed}
        best_match = difflib.get_close_matches(value.casefold(), list(candidates), n=1, cutoff=SUGGESTION_CUTOFF)
        if best_match:
            return f'"{value}" is not a valid {field_name}: did you mean "{candidates[best_match[0]]}"?'
        return f'"{value}" is not a valid {field_name} (allowed: {", ".join(allowed)})'

    def run(self, *, overwrite: bool = True, publish: bool = False) -> tuple[Collaboration, bool]:
        """
        Write the record to the database, creating the collaboration or updating the matching one.

        The matching collaboration is locked and read again, so that the values shown to the operator
        by :py:meth:`compare` cannot be silently replaced by a concurrent edit.

        :param overwrite: Whether the values of a collaboration already in the database must be
            replaced by the record's ones. Ignored when the collaboration is created.
        :type overwrite: bool
        :param publish: Whether the public listing flag of a collaboration already in the database must
            be set. Collaborations created by the import are always approved for public listing.
        :type publish: bool
        :raises ValidationError: If the record cannot be imported (see :py:meth:`validate`).
        :return: The imported collaboration and whether it has been created.
        :rtype: tuple[Collaboration, bool]
        """
        self.validate()
        with transaction.atomic():
            self._instance = None
            instance = self.get_existing(lock=True)
            created = instance is None
            if created:
                instance = Collaboration(name=self.name, public_listing=True)
            elif publish:
                instance.public_listing = True
            if created or overwrite:
                for field_name, value in self.get_values().items():
                    setattr(instance, field_name, value)
            if not self.dry_run:
                instance.save()
        self._instance = instance
        return instance, created
