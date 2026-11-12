import logging

import pytest
from django import forms
from django.http import HttpRequest
from journal.models import Journal
from plugins.wjs_submission.fields import WjsMiniHTMLFormField
from plugins.wjs_submission.helpers.forms import FIELD_SPECS, map_dynamic_field
from plugins.wjs_submission.step1.forms import SubmissionStep1Form
from submission.models import Article, Field, FieldAnswer, field_kind_choices
from utils.forms import HTMLDateInput


def _element(journal: Journal, kind: str, **kwargs) -> Field:
    """Create a displayed submission field element for the journal."""
    defaults = {
        "journal": journal,
        "name": f"extra_{kind}",
        "kind": kind,
        "required": False,
        "display": True,
        "order": 1,
        "help_text": "Some help",
        "choices": "first|second",
    }
    return Field.objects.create(**{**defaults, **kwargs})


@pytest.mark.parametrize(
    ("kind", "field_class", "widget_class"),
    [
        ("text", forms.CharField, forms.TextInput),
        ("textarea", WjsMiniHTMLFormField, None),
        ("check", forms.BooleanField, forms.CheckboxInput),
        ("date", forms.CharField, HTMLDateInput),
        ("select", forms.ChoiceField, forms.Select),
        ("email", forms.EmailField, forms.EmailInput),
    ],
)
@pytest.mark.django_db
def test_map_dynamic_field_builds_the_field_for_each_kind(journal, kind, field_class, widget_class):
    """Every Janeway field kind is mapped to the expected form field and widget."""
    form_field = map_dynamic_field(_element(journal, kind), None)

    assert type(form_field) is field_class, f"{kind} builds a {field_class.__name__}"
    if widget_class:
        assert type(form_field.widget) is widget_class, f"{kind} uses a {widget_class.__name__}"


@pytest.mark.django_db
def test_field_specs_cover_every_janeway_field_kind():
    """The spec table covers all the kinds Janeway offers, so none is silently left out."""
    janeway_kinds = {kind for kind, _ in field_kind_choices()}

    assert set(FIELD_SPECS) == janeway_kinds, "FIELD_SPECS and Janeway field kinds match"


@pytest.mark.django_db
def test_map_dynamic_field_select_renders_the_element_choices(journal):
    """A select element offers its bar-separated choices."""
    form_field = map_dynamic_field(_element(journal, "select"), None)

    assert [label for value, label in form_field.choices if value] == ["first", "second"], (
        "choices come from the element"
    )


@pytest.mark.parametrize("required", [True, False])
@pytest.mark.django_db
def test_map_dynamic_field_select_starts_with_a_blank_choice(journal, required):
    """A select has no preselected answer: the first choice is blank, so a required select must be actually chosen."""
    form_field = map_dynamic_field(_element(journal, "select", required=required), None)

    assert not form_field.choices[0][0], "the first choice is blank"
    if required:
        with pytest.raises(forms.ValidationError):
            form_field.clean("")
    else:
        assert not form_field.clean(""), "an optional select can be left blank"


@pytest.mark.parametrize(
    ("kind", "required", "expected"),
    [
        ("textarea", True, True),
        ("textarea", False, False),
        ("text", True, False),
    ],
)
@pytest.mark.django_db
def test_map_dynamic_field_marks_required_textarea_as_js_required(journal, kind, required, expected):
    """TinyMCE drops the HTML ``required`` attribute, so a required textarea is flagged for ``detect_required.js``."""
    form_field = map_dynamic_field(_element(journal, kind, required=required), None)

    assert bool(form_field.widget.attrs.get("js_required")) is expected, f"js_required is {expected}"


@pytest.mark.parametrize("kind", ["text", "textarea", "email"])
@pytest.mark.django_db
def test_map_dynamic_field_label_and_required_help_text(journal, kind):
    """The label is the element name; a required element prefixes its help text with "Required"."""
    required = map_dynamic_field(_element(journal, kind, required=True), None)
    optional = map_dynamic_field(_element(journal, kind, name="optional", required=False), None)

    assert required.label == f"extra_{kind}", "the label is the element name"
    assert required.required, "the form field is required"
    assert "Required" in str(required.help_text), "required help text is flagged"
    assert "Some help" in str(required.help_text), "the element help text is kept"
    assert not optional.required, "the form field is optional"
    assert "Required" not in str(optional.help_text), "optional help text is not flagged"


@pytest.mark.django_db
def test_map_dynamic_field_text_shows_help_text_not_placeholder(journal):
    """The help text of a text element is rendered as help text, with no placeholder."""
    form_field = map_dynamic_field(_element(journal, "text"), None)

    assert form_field.help_text == "Some help", "help text is shown as help text"
    assert "placeholder" not in form_field.widget.attrs, "no placeholder is set"


@pytest.mark.django_db
def test_map_dynamic_field_unsupported_kind_raises(journal):
    """An element kind with no spec is a caller error: the helper never returns ``None``."""
    with pytest.raises(KeyError):
        map_dynamic_field(_element(journal, "unsupported"), None)


@pytest.mark.django_db
def test_map_dynamic_field_uses_the_saved_answer_as_initial(journal, article: Article):
    """A saved article with an answer for the element pre-fills the field."""
    element = _element(journal, "text")
    FieldAnswer.objects.create(field=element, article=article, answer="saved answer")

    assert map_dynamic_field(element, article).initial == "saved answer", "the answer is the initial value"
    assert map_dynamic_field(element, Article()).initial is None, "an unsaved article has no initial value"


@pytest.mark.django_db
def test_step1_form_ignores_elements_of_unsupported_kind(
    journal, article: Article, fake_request: HttpRequest, caplog: pytest.LogCaptureFixture
):
    """The step 1 form builds only the additional fields whose kind is supported, and logs the skipped ones."""
    _element(journal, "text", name="supported")
    _element(journal, "unsupported", name="unsupported", order=2)

    with caplog.at_level(logging.WARNING, logger="plugins.wjs_submission.step1.forms"):
        form = SubmissionStep1Form(journal=journal, user=article.owner, instance=article, step=1, request=fake_request)

    assert "supported" in form.fields, "the supported element is added"
    assert "unsupported" not in form.fields, "the unsupported element is left out"
    assert "unsupported kind 'unsupported'" in caplog.text, "the skipped element is logged"
    assert all(form_field is not None for form_field in form.fields.values()), "no form field is None"
