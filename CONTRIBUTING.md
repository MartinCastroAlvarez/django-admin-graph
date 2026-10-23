# Contributing to django-admin-graph

## TL;DR

```bash
poetry install --all-extras
poetry run pytest
poetry run ruff check django_admin_graph tests && poetry run ruff format --check django_admin_graph tests
poetry run mypy django_admin_graph
poetry run bandit -c pyproject.toml -q -r django_admin_graph
poetry run pip-audit
```

Open a PR against `main` from a `feat/…`, `fix/…`, `docs/…` or `chore/…`
branch.

## What this package will not accept

- Permission logic of its own (`user.has_perm`, custom role maps). Ask the
  ModelAdmin.
- Database queries, record data, URLs or user identity in the graph.
- Schema changes without a `SCHEMA_VERSION` bump per
  [`docs/schema.md`](docs/schema.md).

## What it does accept

- New node attributes that the admin already exposes (minor schema bump).
- New exporters under `django_admin_graph/exporters/`.
- Support for new Django versions (add them to the CI matrix and the
  classifiers).
- Docs, examples and tests.

## House rules

1. Every folder has a `README.md`.
2. Tests alongside features; visibility changes need anonymous, non-staff
   and limited-staff cases in `tests/test_security.py`.
3. `schema.py`, `schema.json`, `docs/schema.md` and `CHANGELOG.md` change
   together.
4. No secrets in commits.

## Releasing

1. Bump `version` in `pyproject.toml` and `__version__` in
   `django_admin_graph/__init__.py`; move `Unreleased` in `CHANGELOG.md`
   under the new version.
2. Merge, tag the merge commit `vX.Y.Z`, push the tag. `publish.yml`
   checks tag == version, runs the tests, scans the artefacts and publishes
   through PyPI Trusted Publishing, then creates the GitHub Release.
