## 2026-11-10 — Article submissions admin uses shared article search; unaccent extension
**What:**
- `ArticleSubmissionAdmin` dropped its own `search_fields`, `list_filter` and search override. It now uses wjs-themes' `ArticleSearchFilterMixin` with `article_lookup_prefix = "article__"`.
- Migration `0025_unaccent_extension` creates the PostgreSQL `unaccent` extension.
**Why:** specs#3329. Owner surname ("Munizzi") and correspondence email searches found nothing. All three advanced-admin article pages must share the same search and filters.
**Decisions:**
- **The extension migration lives here, not in wjs-themes.** wjs-themes has no migrations of its own.
- **Tests skip migrations.** A session `django_db_setup` fixture in `tests/conftest.py` creates the extension.
- **Requirement bumped.** wjs-submission now requires `wjs-themes >= 2.1.11`.
**Follow-ups:**
- Deploy this migration with or before wjs-themes 2.1.11.
- Read the full rationale in the wjs-themes entry of the same date.
**Refs:**
- https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3329
- wjs-themes `artifacts/activity-log/2026-11-10-shared-article-admin-search-filters.md`
