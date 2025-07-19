from django.utils.translation import gettext_lazy as _

DIRECTOR_ROLE = "director"
DIRECTOR_MAIN_ROLE = "director-main"
EDITOR_ROLE = "editor"
SECTION_EDITOR_ROLE = "section-editor"
AUTHOR_ROLE = "author"
COAUTHOR_ROLE = "co-author"
REVIEWER_ROLE = "reviewer"
EO_GROUP = "EO"
TYPESETTER_ROLE = "typesetter"

LABELS = {
    DIRECTOR_ROLE: _("Director"),
    DIRECTOR_MAIN_ROLE: _("Director"),
    EDITOR_ROLE: _("Editor"),
    SECTION_EDITOR_ROLE: _("Editor"),
    AUTHOR_ROLE: _("Author"),
    COAUTHOR_ROLE: _("Co-author"),
    REVIEWER_ROLE: _("Reviewer"),
    EO_GROUP: _("EO"),
    TYPESETTER_ROLE: _("Typesetter"),
}


def role_label(role):
    return LABELS.get(role, role)
