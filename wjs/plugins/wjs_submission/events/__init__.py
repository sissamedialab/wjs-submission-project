"""
Submission workflow.
"""


class SubmissionEvent:
    ON_ACCESS_MODE_SELECTION = "on_access_mode_selection"

    # This event will be triggered at the end of the submission of a revision.
    # This event should trigger the journal-specific logic related to revision-submission
    # (notifications, etc.)
    # The logic itself is then in charge of emitting
    # - ON_REVISIONS_COMPLETE and
    # - ON_WORKFLOW_ELEMENT_COMPLETE
    ON_REVISION_SUBMISSION_COMPLETED = "on_revision_submission_completed"
