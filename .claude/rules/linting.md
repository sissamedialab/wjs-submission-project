# Linting & code style rules

Code style is enforced; it is not a matter of personal preference. All code in this repo must
satisfy the configured tools at **line length 119**.

> **Note for anyone porting rules from another `wjs-*` repo:** other repos in this family (e.g.
> `wjs-profile-project`) use a black + isort + flake8 + pydocstyle stack and explicitly avoid
> ruff. **This repo does not** — it switched to ruff. Don't copy that stack's config or
> assumptions here; the tool-by-tool mapping below is this repo's actual, current setup.

## Where config lives

- **`pyproject.toml`** — `[tool.ruff]` (+ `[tool.ruff.format]`, `[tool.ruff.lint]`,
  `[tool.ruff.lint.per-file-ignores]`) and `[tool.djlint]`. There is no `[tool.black]`,
  `[tool.isort]`, or `[tool.pydocstyle]` section — ruff replaces all three.
- **`setup.cfg`** — packaging metadata only (`[metadata]`, `[options]`,
  `[options.extras_require]`, `[options.packages.find]`, `[options.package_data]`). No
  `[flake8]`, `[pycodestyle]`, or `[pydocstyle]` section exists here.

## The gate: pre-commit

`pre-commit` enforces style locally and in CI.

```bash
pip install pre-commit && pre-commit install   # once
pre-commit run --all-files                      # on demand
```

Always run `pre-commit run --all-files` before committing.

## Tool stack (authoritative — `.pre-commit-config.yaml`)

- **pre-commit-hooks** — generic hygiene: trailing whitespace, large files, `check-ast`,
  `check-json`/`check-toml`/`check-yaml`, merge-conflict markers, end-of-file fixer, LF line
  endings, `fix-encoding-pragma --remove` (strips `# -*- coding: utf-8 -*-`, consistent with
  `.claude/rules/code-style-python.md`'s "no encoding pragma" rule).
- **ruff** (`ruff --fix`) — linter. `[tool.ruff.lint]` sets `select = ["ALL"]` plus
  `extend-select = ["I"]` (isort) and a long `ignore` list (docstring exemptions D100/D101/D103/
  D104/D105/D106/D200/D203/D212, annotation rules, `TID252`, complexity rules `C901`/`PLR0912`/
  `PLR1702`, etc. — see `pyproject.toml` for the full, current list). This one tool covers what
  black + isort + flake8 (+ plugins) + pydocstyle would otherwise split across several.
- **ruff-format** (`ruff-format`) — formatter, replaces black. Line length 119
  (`[tool.ruff] line-length = 119`), target `py311`, `preview = true`. Ruff's formatter defaults
  to double-quoted strings and is not overridden in `[tool.ruff.format]`, so the double-quotes
  convention is enforced by the formatter itself — not left inert the way it was under the old
  flake8-based setup.

**Not active in this repo's pre-commit config** (present only as commented-out blocks in
`.pre-commit-config.yaml`, kept for reference / possible future re-enable): pyupgrade,
django-upgrade, isort, black, flake8, codespell. **djlint is configured in `pyproject.toml`
(`[tool.djlint]`, `profile = "django"`, `ignore = "H006"`) but has no corresponding hook in
`.pre-commit-config.yaml`** — running `djlint --profile=django` manually still checks templates
against that config (see `.claude/rules/templates-django.md`), but `pre-commit run` does not run
it for you. Prettier is likewise not wired up here.

CI's `Pre-commit` job (`.gitlab-ci.yml`) extends `.run-pre-commit` from an included template in
`wjs-profile-project`, so it runs the same `.pre-commit-config.yaml` as local — if a rule isn't
enforced locally, it isn't enforced in CI either.

## Style notes

- Double quotes, no encoding pragma, no `u"..."` prefix: enforced (ruff-format for quotes,
  pre-commit-hooks' `fix-encoding-pragma` for the pragma). See `.claude/rules/code-style-python.md`
  for the full style list.
- Docstring rules are enforced by ruff's `D` codes, with the `pyproject.toml` ignore list above —
  this is the authoritative docstring config for this repo (there is no separate/conflicting
  `[pydocstyle]` section anywhere in this repo, unlike some sibling repos).
- Because `select = ["ALL"]`, new files can trip rules that weren't previously relevant (e.g.
  `S`-series security checks, `PL`-series pylint-equivalents) — when a rule genuinely doesn't fit
  this codebase, add it to `[tool.ruff.lint.ignore]` in `pyproject.toml` (with a short comment,
  matching the existing entries) rather than sprinkling `# noqa` everywhere.
- `tests/**` gets its own relaxations via `[tool.ruff.lint.per-file-ignores]` (`S101` bare
  `assert`, `PLR0913`/`PLR0917` many-arguments, `ARG005` unused lambda arg) — check that table
  before assuming a rule applies uniformly.
