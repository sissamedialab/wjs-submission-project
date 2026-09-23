# step1 cover-letter-file resubmission: analysis and fix

- **Status**: approved, implemented in this same session.
- **Scope**: `wjs.plugins.wjs_submission.step1.forms.SubmissionStep1Form.save()` and
  `wjs.plugins.wjs_submission.step1.forms.RevisionConfirmForm.save()` (the latter is inherited,
  unmodified, by `RevisionMetadataForm`/`RevisionFullForm`). Companion tests:
  `tests/test_step1_resubmission.py`.

## Scenario

Step 1 has already been submitted once (a cover-letter *file* is already attached), and the
author goes back to step 1 and re-posts the form. Three variants, in both the plain-submission
form and the revision form:

1. the author does not touch the file field (no new upload, no "clear")
2. the author checks "clear" to remove the existing file
3. the author uploads a new file to replace the existing one

For each we care about: is the *old* `core.models.File` row removed, is the old on-disk file
removed, and — for the "no change" case specifically — does re-posting without any change
needlessly recreate a new file.

## Root cause

Django's `FileField.clean(data, initial)` (`django/forms/fields.py`) returns `initial` whenever
nothing was uploaded and "clear" wasn't checked:

```python
def clean(self, data, initial=None):
    ...
    if data is False:
        ...
        return False
    if not data and initial:
        return initial
    return super().clean(data)
```

Here `initial` is a `plugins.wjs_submission.fields.CoreFileWrapper` wrapping the file already on
disk (set from `article.submission_data.cover_letter_file`, or from
`RevisionStorage.data["cover_letter_file"]` for revisions). `CoreFileWrapper` is truthy, so
`cleaned_data["cover_letter_file"]` ends up being:

| author action | `cleaned_data["cover_letter_file"]` |
|---|---|
| no upload, no clear | `CoreFileWrapper` (truthy!) |
| clear checked | `False` |
| new file uploaded | the uploaded `UploadedFile` (truthy) |

Both `save()` methods only ever branch on *truthy* / `False` / *falsy* — they cannot distinguish
"untouched" from "genuinely new upload", since both are truthy. Consequences (verified in
`tests/test_step1_resubmission.py`, all currently passing — i.e. this is exactly what the code
does today):

- **`SubmissionStep1Form.save()`** (`step1/forms.py:289`): the "no change" case falls into the
  truthy branch and re-saves the wrapped file under a *new* filename/pk
  (`core_files.save_file_to_article` always generates a fresh `uuid4` name) — the file is
  silently **recreated** on every resubmit. Worse, neither the "no change" recreate nor a
  genuinely **new upload** ever delete the *previous* `File` row/disk file — both leak an
  orphaned `File` row and an orphaned file on disk.
- **`RevisionConfirmForm.save()`** (`step1/forms.py:380`, shared by `RevisionFullForm`/
  `RevisionMetadataForm` — the latter doesn't expose the field at all): the "no change" case also
  recreates the file, but this code path already deletes the file referenced by
  `RevisionStorage.data` before writing the replacement, so it does **not** leak orphans — it just
  wastefully recreates an identical file under a new pk/uuid on every untouched resubmit.
- **"Clear"** behaves correctly in both forms today (old `File` row + disk file removed) — nothing
  to fix there.

## Proposed fix

Special-case `CoreFileWrapper` explicitly as "untouched" in both `save()` methods, and make the
plain-submission path delete the previous file before saving a genuine replacement (mirroring
what the revision path already does). This is a `save()`-only change:
`clean()`/`clean_cover_letter_file()` are untouched, so the existing "must provide a cover letter
or comments" mutual-requirement validation is unaffected — the `CoreFileWrapper` stays truthy
there, exactly as before the fix (it still correctly satisfies "a cover letter is provided").

### `SubmissionStep1Form.save()`

```python
cover_letter_file = self.cleaned_data.get("cover_letter_file")
if isinstance(cover_letter_file, CoreFileWrapper):
    # The author didn't touch the file field: FileField.clean() falls back to the initial
    # value (a wrapper around the file already saved on a previous visit to this step).
    # Nothing changed, so there is nothing to do.
    pass
elif cover_letter_file:
    # A genuinely new file: replace the previous one instead of leaving it orphaned.
    if self.instance.submission_data.cover_letter_file:
        self.instance.submission_data.cover_letter_file.delete()
    file = core_files.save_file_to_article(
        file_to_handle=cover_letter_file,
        article=self.instance,
        owner=self.user,
        label="Cover letter",
    )
    file.privacy = "owner"
    file.save()
    self.instance.submission_data.cover_letter_file = file
    self.instance.submission_data.save()
elif cover_letter_file is False:
    # False means that we should clear the existing file
    if self.instance.submission_data.cover_letter_file:
        self.instance.submission_data.cover_letter_file.delete()
    self.instance.submission_data.cover_letter_file = None
    self.instance.submission_data.save()
```

### `RevisionConfirmForm.save()`

```python
if field_name == "cover_letter_file":
    if field_value is None or isinstance(field_value, CoreFileWrapper):
        # Either there was never a file and none was uploaded, or the author left the
        # existing (draft) file untouched - nothing to do.
        pass
    elif field_value is False:
        ...  # unchanged: clear branch already deletes the old file correctly
    else:
        ...  # unchanged: new-upload branch already deletes the old file correctly
```

`CoreFileWrapper` is already imported in `step1/forms.py`, so no import changes are needed.

## Effect on existing tests

Three of the six tests in `tests/test_step1_resubmission.py` documented the *buggy* behavior and
must be updated to assert the *fixed* behavior instead:

- `test_submission_no_change_recreates_the_file_and_orphans_the_old_one` → renamed
  `test_submission_no_change_is_a_true_no_op`: no new `File` is created, the original file/pointer
  is untouched.
- `test_submission_new_upload_replaces_the_pointer_but_orphans_the_old_file` → renamed
  `test_submission_new_upload_replaces_the_pointer_and_removes_the_old_file`: the old `File`
  row/disk file must now be gone.
- `test_revision_no_change_recreates_the_file_but_cleans_up_the_old_one` → renamed
  `test_revision_no_change_is_a_true_no_op`: no new `File` is created at all; the original File
  row/disk file and `RevisionStorage.data` pointer are untouched.

The other three (`clear` in both forms, `revision new upload`) already asserted correct behavior
and are unaffected.
