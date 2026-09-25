## 2026-09-23 — Respect Keyword.deactivated when offering keywords in submission

**What:** `get_keywords_by_journal` and `get_keywords_by_journal_and_arxiv_category` now
exclude deactivated keywords, and carry `Prefetch` objects so the filtering survives all the
way into the step 3 template.

**Why:** Issue #3053 asked only for the two functions to filter on `Keyword.deactivated`. That
alone would have been a no-op in production for every hierarchical journal — JHEP, **JCAP**
(the journal the issue was filed for), JSTAT, JINST, JQuant. Those journals get a queryset of
top-level `KeywordGroup`s, and `step3/article_form.html` renders its leaf checkboxes from
`group.keywords.all` / `subgroup.keywords.all` — raw reverse relations no amount of
group-level filtering touches. The prefetches are what make the fix real.

**Decisions:**
- Fix stays inside `keywords.py` via `Prefetch`, rather than pushing filtering into the
  template. The template is left untouched.
- Two adjacent bugs fixed in passing because they're the same query: `group.keywords.all` is
  now journal-scoped (a group shared across journals used to leak the other journal's
  keywords into the form), and subgroups are ordered by `KeywordGroup.order` instead of
  undefined DB order.
- POST-side validators (`jquant_`/`jhep_`/`basic_keyword_selection_rule`) deliberately left
  alone — scoped out by the user. See Follow-ups.
- Skipped the spec/plan documents: bounded bugfix, ~2h of work.

**Gotcha worth remembering:** `QuerySet.exists()` does **not** bypass a prefetch cache.
`exists()` returns `bool(self._result_cache)` when the cache is populated, and a prefetched
related manager's `get_queryset()` returns exactly such a queryset. We changed
`{% if group.keywordgroup_set.exists %}` to `.all` believing the guard bypassed the cache and
was load-bearing; reverting the template and re-running the regression test proved it wasn't,
so the change was dropped. The behaviour test it motivated was kept — it pins the rule that a
group whose subgroups are all emptied still offers its own direct keywords.

**Agent usage:**

| Stage | Agent/skill | Tokens | Time |
|---|---|---|---|
| Design | superpowers:brainstorming | inline | ~5m |
| Implementation | (inline, TDD) | inline | ~35m |
| Review | superpowers:requesting-code-review (general-purpose subagent) | ~130k | ~17m |
| Review | nephila-core-conventions:code-eval | inline | ~5m |
| Review | nephila-core-conventions:doc-sync | inline | ~3m |

**Considered & dropped:**
- Literal issue scope only (filter the two functions, leave the hierarchical gap) — would
  have closed the issue without fixing JCAP.
- Filtering in the template instead of the queryset — pushes query logic into presentation.
- Hardening the POST-side validators in the same change — real but separate hole; kept the
  diff scoped to the issue.

**Follow-ups:**
- The keyword validators still accept a deactivated keyword id submitted via POST (stale tab
  or crafted request). Flat journals don't even reach them: their checkboxes post into
  Janeway's `KeywordModelForm.keywords`, whose queryset is unfiltered. Worth its own issue.
- A keyword deactivated after an author selected it now disappears from step 3 and is dropped
  on the next save, silently. Deliberate, but the author gets no notice.
- `pytest-freezegun` 0.4.2 is broken on Python 3.13 (`distutils` removed); local runs need
  `-p no:freezegun`. Pre-existing, unrelated to this work, but it blocks any local test run.

**Eval:** 84% — artifacts/evaluations/2026-09-23-respect-keyword-deactivated.md

**Refs:** [wjs/specs#3053](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3053),
branch `bugfix/issue-3053-respect-keyword-deactivated`.
