# CLAUDE.md

Contract between this repository and any AI agent contributing to it.

## Required reading

1. This file. 2. [`README.md`](README.md). 3. [`ARCHITECTURE.md`](ARCHITECTURE.md).
4. [`SECURITY.md`](SECURITY.md). 5. [`docs/schema.md`](docs/schema.md) before touching `schema.py`.

## Mission

`django-admin-graph` introspects a Django `AdminSite` into a typed,
versioned graph. It is the building block `django-admin-skills` consumes,
so **the JSON schema is the product**.

## The rules

1. **The admin is the only source of permissions.** Read them from
   `AdminSite.has_permission`, `ModelAdmin.has_*_permission`,
   `get_model_perms`, `get_actions`, `get_inline_instances`. Never
   `user.has_perm(…)`, never re-derive.
2. **Never query rows.** No `Model.objects…` in `django_admin_graph/`.
3. **Never name what the user cannot see.** Invisible models are not
   nodes; relations to them have `target: null`.
4. **Staff-only by default.** The view stays `GET`/`HEAD`, no
   `@csrf_exempt`, `Cache-Control: private, no-store`.
5. **Schema changes follow `docs/schema.md`.** New optional key → minor
   bump of `SCHEMA_VERSION`; rename/removal → major. Update `schema.py`,
   `schema.json`, `docs/schema.md` and `CHANGELOG.md` together.
6. **Every folder has a `README.md`.**

## Done means

`poetry run pytest` (coverage ≥ 90%), `ruff check`, `ruff format --check`,
`mypy` (strict), `bandit`, `pip-audit` all green; docs and CHANGELOG updated
in the same change; new behaviour has a test for anonymous, non-staff and
limited-staff users when it touches visibility.

## Git

Small commits, imperative subjects, never force-push `main`, never commit
secrets, never bypass hooks.
