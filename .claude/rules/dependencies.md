# Dependency boundaries

`wjs-submission` is a standalone Janeway plugin: CI installs only Janeway and this plugin.

- **Never import Python code** from `wjs-profile-project` (`wjs.jcom_profile`, `wjs.plugins.wjs_review`, ...) or
  `wjs-search-user` (`wjs.user_search`), in production code or in tests.
- **When using URLs from `wjs-profile-project` or `wjs-search-user`** (e.g. `{% url 'search-typeahead' %}` in a
  template), write proper stubs in tests: they are not resolvable in this repo's CI, even if they are locally
  because your Janeway checkout has those projects installed. See `_reverse_with_stubs` in
  `tests/test_required_markers.py` for an example.
