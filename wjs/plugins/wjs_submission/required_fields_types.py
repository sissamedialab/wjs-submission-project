"""
Types of the per-journal required profile fields of a correspondence author.

This module must stay free of model imports: it is imported by settings modules, which are loaded before the apps.
The entries stay plain dicts at runtime (settings are written and overridden as dicts): the types only document the
format and let type checkers and tests verify it.
"""

from typing import NotRequired, TypedDict

from django.utils.functional import Promise


class RequiredFieldEntry(TypedDict):
    """
    One required profile field of a correspondence author.

    Installing projects may add keys of their own (e.g. wjs-profile-project's `profile` hint) by subclassing this
    type; wjs-submission ignores them.
    """

    label: str | Promise
    """Public, translatable label shown to the author in submission step 4 when the entry is not satisfied."""

    paths: list[str]
    """
    Dotted attribute paths on the user account (e.g. `last_name`, `jcomprofile.profession`).

    Callables (e.g. `affiliation`) are called. A path that cannot be resolved raises.
    """

    allowed: NotRequired[list]
    """
    Accepted values.

    Without it the entry is satisfied if ANY path has a truthy value; with it, if ANY path value is in `allowed`
    (no truthiness test, so e.g. 0 can be valid).
    """


RequiredFieldsByJournal = dict[str | None, list[RequiredFieldEntry]]
"""Journal code -> entries; the `None` key is the fallback for journals without their own."""
