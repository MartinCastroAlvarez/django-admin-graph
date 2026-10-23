## Summary

<!-- What changed and why. -->

## Checklist

- [ ] `poetry run pytest` passes; visibility changes have anonymous / non-staff / limited-staff tests
- [ ] ruff check, ruff format --check, mypy, bandit, pip-audit pass
- [ ] No permission logic of our own, no row queries in `django_admin_graph/`
- [ ] Schema changes bump `SCHEMA_VERSION` and update `schema.json`, `docs/schema.md`, `CHANGELOG.md`
- [ ] No secrets in the diff
