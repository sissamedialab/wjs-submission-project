## 2026-10-06 — Copy arXiv category to errata and addenda
**What:** New errata/addenda inherit `ArticleSubmission.arxiv_category` from the corrected
article, and migration `0024_backfill_correction_arxiv_category` fills it on existing ones.
The article page (`wjs_article_details`) now shows "arXiv id (category)" for corrections too.

**Why:** #3212 (JCAP EO): the page already renders `({{ submission_data.arxiv_category }})`,
but corrections skip the arXiv step and `SetupCorrectionStorage` copied only the arXiv
*identifier*, so errata/addenda showed empty brackets.

**Decisions:**
- Copy at creation time (snapshot), like the arXiv id and the other metadata in
  `_populate_metadata`, instead of reading through the Hydra link at render time.
- Backfill as a data migration (user's call) rather than a one-off command; it only fills
  empty categories, never creates `ArticleSubmission` rows, and is idempotent. Body lives in
  `data.py` (same pattern as `0008`) so tests can call it directly.
- Hard dependency on `("hydra", "0001_initial")`: Hydra is effectively mandatory (unguarded
  import in `correction/logic.py` loaded by the plugin URLconf; `jcom_profile.0042` already
  depends on it). The `ImportError` guards in `workflow.py`/`mixins.py` are leftovers.
  `0001_initial` rather than `0002` because only `from_article`/`to_article`/`relationship`
  are read.

**Gotcha worth remembering:** an `Article` `post_save` signal (`signals.py`) creates an
`ArticleSubmission` and caches *that* instance on `article.submission_data`. In
`_populate_metadata`, writing to the instance returned by `get_or_create` was silently
wiped when the access-mode block re-saved `self.to_article.submission_data`. Always write
through `to_article.submission_data`. Same signal means tests must `update()`/`delete()`
the auto-created row, not `create()` one.

**Agent usage:**

| Stage | Agent/skill | Tokens | Time |
|---|---|---|---|
| Design | superpowers:brainstorming (inline) | ~60k | ~15m |
| Design | superpowers:writing-plans (inline) | ~30k | ~8m |
| Implementation | superpowers:executing-plans (inline) | ~80k | ~15m |
| Review | code reviewer subagent (Opus) | ~65k | ~3.5m |
| Review | code-eval + doc-sync (inline) | ~15k | ~3m |

Eval: 80% — artifacts/evaluations/2026-10-06-correction-arxiv-category.md

**Considered & dropped:** conditional/optional Hydra dependency in the migration (Hydra is
not optional); management command for the backfill (must be remembered per environment).

**Follow-ups:**
- `makemigrations --check` reports a pending `0025` proxy migration for `CollaborationProxy`
  (`advanced_admin.py`), pre-existing and unrelated: needs its own ticket.
- Locally `pytest-freezegun` breaks on Python 3.13 (`distutils`); run with `-p no:freezegun`.
- Deferred review minors: backfill does 2 SELECTs per link; no setup test for a source
  `ArticleSubmission` with an empty category.

**Refs:** wjs/specs#3212; spec `artifacts/specs/2026-10-06-correction-arxiv-category-design.md`;
plan `artifacts/plans/2026-10-06-correction-arxiv-category.md`.
