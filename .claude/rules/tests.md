# Testing rules

This repo is a set of Django apps/plugins that live **inside Janeway** — tests cannot run from this directory in isolation. They need a full Janeway environment.

## Normal local workflow — run from `janeway/src`

Run pytest **from the `janeway/src` directory**, pointing at this repo by relative path — this
repo has no `pytest.ini` (unlike some sibling `wjs-*` repos), so pytest auto-discovers this repo's
`pyproject.toml` (`[tool.pytest.ini_options]`) as its config from that path instead.

```bash
# from janeway/src/, with janeway and wjs-submission-project checked out as siblings
# (e.g. both directly under the same parent directory)
pytest --create-db -n7 ../../wjs-submission-project
```

For a single test, keep the same repo-relative path, just add the test node id:

```bash
pytest ../../wjs-submission-project/tests/test_file.py::TestClass::test_name
```

Two things must already be true in the Janeway checkout for this to work — both are one-time
setup, not something you redo per test run:

- **This repo installed editable into Janeway's virtualenv:** `pip install -e .[test]` (run from
  this repo). Verify with `pip show wjs-submission` — `Editable project location` must point at
  this checkout; otherwise `plugins.wjs_submission` resolves to a stale copy instead of your
  working tree.
- **The plugin symlinked into Janeway's own `plugins/` folder:** `janeway/src/plugins/wjs_submission`
  must be a symlink to this repo's `wjs/plugins/wjs_submission/` — this is how Janeway's app loader
  finds it (see *Namespace packages* in the top-level `CLAUDE.md`). `setup_environment`'s "Linking
  plugins..." step does this for CI; locally, create it once with `ln -s`.

You also need a reachable Postgres and Redis (`DATABASES`/`REDIS_*_URL` come from
`wjs.defaults.settings_submission` unless overridden by a local, non-committed `core.settings`
package inside `janeway/src/core/`, which `wjs.defaults.tests_submission` imports automatically —
via `from core.settings import *` — if present).

## Useful invocations

- **Single test:** append `::TestClass::test_name` to the repo-relative path shown above.
- **Reuse DB (default):** `--reuse-db`; force a rebuild with `--create-db`
- **Parallel:** `-n<N>` (e.g. `-n7`)
- **Skip one-shot data-migration command tests:** `-m "not fix_labels"` (CI uses this)

## Key facts (`pyproject.toml`)

> **Note for anyone porting rules from another `wjs-*` repo:** this repo has no `pytest.ini` —
> config lives in `pyproject.toml`'s `[tool.pytest.ini_options]`, and the settings module and test
> locations below are this repo's own, not `wjs-profile-project`'s.

- `DJANGO_SETTINGS_MODULE = "wjs.defaults.tests_submission"` — merges Janeway's global settings
  with `wjs.defaults.settings_submission`.
- `addopts = ["--reuse-db", "--ignore=api", "--ignore=plugins"]` — Janeway's own `api/` and
  `plugins/` test dirs are deliberately ignored (they fail to import outside their app registry).
- Tests run in parallel and reversed (`pytest-reverse`) in CI to catch ordering dependencies.
- Migrations are skipped in tests (`IN_TEST_RUNNER` + `SkipMigrations` in
  `wjs/defaults/tests_submission.py`); data normally created by migrations must be recreated via
  fixtures in `tests/conftest.py` (see e.g. its `install_plugins` autouse fixture).
- Test location: `tests/` at this repo's root.

## Docker = CI replication only

The `docker-compose-test-*.yml` files reproduce the CI test environment. They are **not** part of the day-to-day workflow — use them only when local tests and CI disagree and you need to reproduce CI exactly. Inside the container, `setup_environment` is the bootstrap (also what CI runs).

> **Never commit migrations generated inside the docker env** — they are spurious (they exist only to sync translation fields there).

## TDD cycle

1. Write a failing test (red)
2. Write the minimal code to make it pass (green)
3. Refactor — keep tests green throughout

## Pytest conventions

- Test files: `test_<module>.py`
- Test functions: `test_<description>`
- Fixtures in `conftest.py`
- Use descriptive assertions — no bare `assert` without a message

## Coverage

- New code must be covered; aim for 90%+ — a convention, not a gate any CI job currently enforces.
- **No coverage tooling is configured in this repo** — there's no `tox.ini`, no `.coveragerc`, no
  `[tool.coverage]` section in `pyproject.toml`, and `coverage`/`pytest-cov` aren't listed in
  `setup.cfg`'s `test` extras. `tox -e coverage` does **not** work here (there's no `tox.ini` to
  give it a `coverage` environment to run) — that's `wjs-profile-project`'s command, don't port it.
- To get a coverage report today, install `pytest-cov` yourself and pass `--cov` explicitly (from
  `janeway/src`, per the *Normal local workflow* section above):
  ```bash
  pip install pytest-cov  # not a declared dependency of this repo
  pytest --create-db -n7 ../../wjs-submission-project --cov=wjs --cov-report=term-missing
  ```

## Integration vs unit

- **Unit tests**: mock external services; test logic in isolation
- **Integration tests**: use a real database — never mock the Django ORM; test views and model interactions end-to-end
