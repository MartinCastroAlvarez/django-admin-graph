# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The graph's own `schema_version` is versioned separately (see `docs/schema.md`).

## [Unreleased]

## [0.1.0] — 2026-10-23

### Added
- `build_graph(site=None, request=None, *, app_labels=None) -> AdminGraph`:
  apps, models, fields (types, choices, null, help_text), ModelAdmins
  (list_display, list_filter, search_fields, fieldsets, read-only fields,
  actions, inlines, URL names), inlines and permissions as nodes; FK / O2O /
  M2M, contains, admin-of, inline-of and permission-of edges.
- Request mode: visibility from `AdminSite.has_permission`,
  `has_module_permission`, `get_model_perms`, `get_actions`,
  `get_inline_instances` — hidden models are never named.
- Graph schema `1.0`, documented in `docs/schema.md` and published as
  `django_admin_graph/schema.json`; `AdminGraph.from_dict` for Django-free
  consumers.
- Exporters: JSON, Mermaid `erDiagram`, GraphViz DOT, `networkx`
  (`[networkx]` extra).
- `manage.py admin_graph --format json|mermaid|dot` with `--app`, `--site`,
  `--output`, `--indent`.
- Optional staff-only `GET` view: `include("django_admin_graph.urls")`.
- Django 4.2–6.1 on Python 3.11–3.13.
