# Architecture

## One-line summary

`build_graph(site, request)` asks the admin — never the database, never
`has_perm` — what `request.user` can see, and returns frozen dataclasses
that serialise to a versioned JSON document.

```
AdminSite ──▶ builder._Builder ──▶ AdminGraph (schema.py) ──▶ exporters/ (json · mermaid · dot · networkx)
   ▲              │                        │
   │   has_permission / has_*_permission   ├──▶ views.graph_view   (GET, staff only)
   │   get_actions / get_inline_instances  └──▶ manage.py admin_graph (offline, system user)
ModelAdmin ◀──────┘
```

## Package layout

```
django_admin_graph/
├── __init__.py      — public API re-exports + __version__
├── apps.py          — AppConfig
├── conf.py          — DJANGO_ADMIN_GRAPH settings (ADMIN_SITE, EXCLUDE_APPS, EXCLUDE_MODELS)
├── schema.py        — the typed graph: nodes, edges, to_dict/from_dict, SCHEMA_VERSION
├── schema.json      — JSON Schema of the document (validated in tests)
├── builder.py       — build_graph(): access gate, visibility pass, node/edge construction
├── exporters/       — to_json, to_mermaid, to_dot, to_networkx
├── views.py, urls.py — optional staff-only JSON view
└── management/commands/admin_graph.py — CLI
```

## The build, step by step

1. **Gate** (`check_access`): `request.user` authenticated, then
   `site.has_permission(request)`. Without a request, `system_request()`
   supplies an unsaved `SystemUser` whose `has_perm` is always true.
2. **Visibility pass**: iterate `site._registry` sorted by label; keep a
   model when `has_module_permission(request)` and any value of
   `get_model_perms(request)` is true; drop settings exclusions.
3. **Per model**:
   - *Form shape*: change form via `get_fields/get_readonly_fields/get_fieldsets(request, placeholder)`
     where `placeholder = Model()` (unsaved) if the user may view/change;
     add form via the same getters with `obj=None` if they may add. A
     ModelAdmin that cannot handle an unsaved object falls back to the add form.
   - *Fields*: concrete + M2M fields that the form, read-only fields or
     `list_display` mention, plus the pk. Relation targets are model ids
     only if the target passed the visibility pass.
   - *Admin node*: request-aware getters; `get_actions(request)`
     (handles both pre-6.1 tuples and 6.1 `Action` objects).
   - *Inline nodes*: `get_inline_instances(request)` plus each inline's
     own `has_*_permission`.
   - *Permission nodes*: `default_permissions` + `Meta.permissions`;
     `granted` from the ModelAdmin for the four built-ins, `null` for custom.
4. **Assemble** `AdminGraph` with deterministic ordering.

## Why these choices

- **`_registry` over `get_app_list`**: `get_app_list` reverses admin URLs
  and fails when the site is not mounted (offline tooling); the visibility
  rule it applies is reproduced from the same public ModelAdmin methods.
- **URL names, not URLs**: names are stable and reveal no host or prefix.
- **Frozen dataclasses + JSON Schema** rather than pydantic: zero runtime
  dependencies beyond Django; consumers without Django use `from_dict`.
