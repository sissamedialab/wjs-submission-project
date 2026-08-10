# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`wjs-submission` is a **Janeway plugin** (Janeway is an open-source journal-management system this
repo does not contain — it lives in a sibling checkout, `janeway/src`). The plugin implements the
WJS-specific article submission wizard plus supporting features: ArXiv import, hierarchical
keywords, extended file/content-type support, an "access mode" (open-access/funding) workflow,
Collaborations, and article revision handling.

It is installed *into* a Janeway instance, not run standalone — see `.claude/rules/tests.md` for
why tests need a full Janeway environment, and the *Testing* section below for the specifics of
this repo.

Detailed process rules already live under `.claude/rules/` (branching/commits, linting tool stack,
Django/Python code style, template formatting, testing workflow, architecture principles) and are
loaded automatically — this file only adds what those don't cover: repo-specific commands and the
"read five files to understand this" architecture.

## Commands

```bash
# Install into Janeway's virtualenv (from this repo)
pip install -e .[test]

# Run this repo's tests — from janeway/src, pointing at this repo by relative path
# (from janeway/src/)
pytest --create-db -n7 ../../wjs-submission-project

# Single test
pytest ../../wjs-submission-project/tests/test_workflow.py::TestClass::test_name

# Lint / format — see the discrepancy note below before trusting .claude/rules/linting.md here
pre-commit run --all-files
```

### Testing — repo-specific settings module

Unlike some sibling `wjs-*` repos, this repo has **no `pytest.ini`** — pytest config lives in
`pyproject.toml`'s `[tool.pytest.ini_options]`, which sets:

```
DJANGO_SETTINGS_MODULE = "wjs.defaults.tests_submission"
addopts = ["--reuse-db", "--ignore=api", "--ignore=plugins"]
```

`wjs/defaults/tests_submission.py` merges Janeway's `core.janeway_global_settings`, an optional
local (non-committed) `core.settings`, and `wjs/defaults/settings_submission.py`'s
`INSTALLED_APPS`/middleware, then skips migrations (`IN_TEST_RUNNER` / `SkipMigrations`) the same
way described in `.claude/rules/tests.md`. Data normally created by migrations must be recreated
via fixtures — see `tests/conftest.py` (`install_plugins` autouse fixture, `set_general_settings`,
`JOURNAL_CODE = "JCOM"`).

CI does **not** use this pytest-native path: `setup_environment` copies `cicd_settings.py` /
`cicd_test_settings.py` into Janeway's `core/` as `core.cicd_settings` /
`core.cicd_test_settings` (themselves thin wrappers around
`wjs.defaults.settings_submission` / `wjs.defaults.tests_submission` with CI's Postgres
`DATABASES`), installs plugins/themes the "Janeway way", and loads a prepared DB dump
(`janeway-db-dump.sql.bz2`) before running `pytest`. Regenerating that dump is documented as a
comment inside `setup_environment` itself. Local dev normally does **not** need any of this —
`--reuse-db`/`--create-db` against your own Janeway checkout is enough; reach for
`docker-compose-test-local.yml` only to reproduce CI exactly (per `.claude/rules/tests.md`).

### Linting tool stack: ruff, not black/isort/flake8

Unlike some sibling `wjs-*` repos, this repo's `.pre-commit-config.yaml` runs only the generic
`pre-commit-hooks` plus **ruff** (`ruff --fix` + `ruff-format`) — black, isort, flake8 and
pydocstyle are not active here (`setup.cfg` is pure packaging metadata; `pyproject.toml` has no
`[tool.black]`/`[tool.isort]`/`[tool.pydocstyle]`). `djlint` is configured in `pyproject.toml`
(`[tool.djlint]`) but has no pre-commit hook — run `djlint --profile=django` manually to lint
templates. `.claude/rules/linting.md` documents this repo's actual tool-by-tool mapping in full;
it explicitly flags that it diverges from the black/isort/flake8 convention used elsewhere in the
`wjs-*` family, so don't port linting assumptions from those repos here.

**Outstanding fix needed:** `.claude/rules/templates-django.md` describes a `djlint-django`
pre-commit hook as if it already runs (e.g. "`.pre-commit-config.yaml` only wires up the
`djlint-django` hook", "`pre-commit run djlint-django --all-files` — the actual hook, same as
CI"). That hook does not exist in `.pre-commit-config.yaml` today — templates are currently
linted only by running `djlint --profile=django` manually, never by `pre-commit run` or CI. To
resolve the inconsistency, add a `djlint-django` hook (from the upstream `djLint` pre-commit repo,
pinned to a real released tag — verify the hook id and version against the current
`.pre-commit-hooks.yaml` before adding it) to `.pre-commit-config.yaml`, so the file matches what
`templates-django.md` already documents.

## Architecture

### Namespace packages, no `__init__.py`

`wjs/`, `wjs/defaults/`, `wjs/plugins/` are namespace packages (`find_namespace:` in
`setup.cfg`) — none of them have an `__init__.py`. `setup_environment` symlinks every
`wjs/plugins/wjs*` directory into Janeway's own `plugins/` folder, which is how Janeway's app
loader discovers `plugins.wjs_submission` at runtime; imports throughout the codebase use that
Janeway-side path (`from plugins.wjs_submission... `), not `wjs.plugins.wjs_submission`.

### Plugin registration

`wjs/plugins/wjs_submission/plugin_settings.py` defines the `WJSSubmission(plugins.Plugin)` class
Janeway's plugin machinery discovers (`install()`, `hook_registry()`), plus
`DEFAULT_UNIQUENESS_CHECK` — a dotted-path registry (overridable via
`settings.SUBMISSION_UNIQUENESS_CHECK`) mapping journal code → the callable in
`unique_check.py` that enforces per-journal article-uniqueness rules. This is the
Registry/Decorator extension point described in `.claude/rules/architecture-django.md`; new
per-journal behaviour is added by registering a new dotted path here, not by branching core code.

### The submission wizard: `step1/` … `step8/`

The submission flow is a Django wizard with **one package per step** (`step1` through `step8`),
each holding `forms.py` + `views.py`, and — where side effects are needed — a `logic.py` business
class following the dataclass pattern from `.claude/rules/architecture-django.md` (e.g.
`step3/logic.py`'s `HandleKeywordSelection`: `parse_keyword_weights` → `run_validator` → `persist`,
orchestrated by `run()`). `workflow.py` is the map of the whole wizard: `Step`/`StepState`
describe each step's URL/label/completion state, `STEPS` is the ordered registry views and
templates consult to render the step progress bar, and the `step_check_*`/`is_revision*` helpers
decide whether a given step is complete/skippable for a given `Article` — this is the single
source of truth for wizard navigation logic; don't duplicate step-order or completion checks in
views.

**Outstanding fix needed:** `SubmissionStep1Form.save()` and `SubmissionStep3Form.save()` catch a
business-logic class's `ValidationError`, call `self.add_error(None, e)`, and re-raise — matching
`.claude/rules/architecture-django.md`'s form-side contract. But `SubmissionStep1View` and
`SubmissionStep3View` (`step1/views.py`, `step3/views.py`) have **no `form_valid` override** to
catch that re-raised exception, unlike `step4`/`step5`/`step6`/`step7`/`step8`'s views which do
override `form_valid`/`form_invalid` (for other reasons — see `.claude/rules/architecture-django.md`'s
*Views architecture* section). Today, a `ValidationError` raised inside either form's `save()`
propagates as an unhandled error instead of re-rendering step1/step3 with the message attached.
Fix: add a `form_valid` override to both views that wraps `super().form_valid(form)` in
`try`/`except ValidationError: return super().form_invalid(form)` (the sample pattern in
`architecture-django.md`).

### Revisions reuse the wizard

`revision/logic.py` handles the three depths of post-review revision (`RevisionStartConfirmView`
/ `-Metadata` / `-Full`, wired in `urls.py`): `BaseSetupRevisionStorage` and its
`SetupRevisionStorage{Confirm,Metadata,Full}` subclasses snapshot the current step1/4/5/6/7 state
into `RevisionStorage`/`RevisionArticleAuthorOrder`/`RevisionArticleCollaboration`/
`RevisionSubmissionArticleFunding` (see `models.py`) before letting the author re-edit through the
*same* step views — `workflow.py`'s `is_revision*`/`is_submission` helpers are what make step
views behave differently depending on whether the `Article` is a fresh submission or mid-revision.

### Models (`models.py`)

- `ArticleSubmission` — the plugin's 1:1 extension of Janeway's `submission.Article`, carrying the
  wizard's extra state.
- `AccessMode` / `AccessModeJournal` — configurable open-access/licence/copyright presets per
  journal, resolved through `access_mode.py`'s `AccessModeConfiguration`.
- `Collaboration` / `ArticleCollaboration` / `CollaborationRelation` — the Collaborations feature
  (e.g. consortia authorship) mentioned in the README.
- `RevisionStorage` and its `RevisionArticle*`/`RevisionSubmissionArticleFunding` siblings — the
  revision snapshot tables described above.
- `SubmissionArticleFunding` — extends Janeway's own `ArticleFunding`.

### Other supporting modules worth knowing before you go looking

- `arxiv.py` — ArXiv metadata/PDF/source import (used by step1 and `ArxivMicroservice` in
  `views.py`).
- `keywords.py` / `helpers/keywords.py` — hierarchical keyword groups and per-journal keyword
  count ranges (`KEYWORDS_INTERVAL_PER_JOURNAL`); `management/commands/import_keywords_json.py`
  and `enable_hierarchical_keywords.py` seed/migrate this data.
- `account_validation.py` — author/account validation rules used across the wizard.
- `mixins.py` — `AuthorFilteringView` and friends: view-level access control (own vs.
  correspondence-author articles, optional `WJS_REQUIRE_STAFF_FOR_SUBMISSION`).
- `conversion.py` — file format conversion for uploaded manuscripts.
- `advanced_admin/` — a custom Django-admin-style interface distinct from Janeway's own admin.
- `wjs/defaults/settings_submission.py` — the plugin's default Django settings (captchas, ORCID,
  OIDC, languages, Redis cache/`Q_CLUSTER`, `SUBMISSION_ARTICLE_LANGUAGES` per journal) merged
  into Janeway's settings by whatever installs the plugin.

### Settings module map

| Module | Purpose |
|---|---|
| `wjs/defaults/settings_submission.py` | Plugin defaults (real Django settings) |
| `wjs/defaults/tests_submission.py` | Pytest settings — merges Janeway global settings + the above, skips migrations |
| `cicd_settings.py` (repo root) | CI-only: `settings_submission` + CI Postgres `DATABASES`, copied to Janeway's `core/` by `setup_environment` |
| `cicd_test_settings.py` (repo root) | CI-only: `tests_submission` + CI Postgres `DATABASES`, ditto |

## Deployment note

`.gitlab-ci.yml` pulls its build/deploy/pre-commit job templates from the **`wjs-profile-project`**
repo (`include: project: 'wjs/wjs-profile-project' ref: wjs-production`) — this repo has no
deploy/build templates of its own. Only the `run-tests` job is defined locally, because (per its
inline comment) "the pytest command line is different" from the shared template.
