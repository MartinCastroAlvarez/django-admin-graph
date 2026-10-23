# Graph schema — version 1.0

This is the contract between `django-admin-graph` and anything that reads
its output (`django-admin-skills`, ERD tools, your scripts). The
machine-readable form is
[`django_admin_graph/schema.json`](../django_admin_graph/schema.json)
(JSON Schema 2020-12); the test suite validates every generated graph
against it.

## Versioning

`schema_version` is `"MAJOR.MINOR"`.

- **Minor** bump: a new optional key, node kind or edge kind. Old readers
  keep working.
- **Major** bump: a key renamed or removed, or a value's meaning changed.
- Readers must **refuse an unknown major** (`AdminGraph.from_dict` raises
  `SchemaVersionError`) and **ignore unknown keys and node kinds**
  (`from_dict` does).

The package version and the schema version are independent: many package
releases can share one schema version.

## Document

```json
{
  "schema_version": "1.0",
  "generator": {"name": "django-admin-graph", "version": "0.1.0"},
  "site": {"name": "admin", "site_header": "Django administration", "site_title": "Django site admin"},
  "scope": {"mode": "request"},
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

| Key | Meaning |
| --- | --- |
| `scope.mode` | `"request"` — filtered for one user's admin permissions. `"system"` — built offline for an unrestricted, unsaved system user (the shape an active superuser sees). |
| `site.name` | The `AdminSite.name`; also the namespace of every `url_names` entry. |
| `nodes` | Ordered: all `app` nodes, then per model `model`, `admin`, its `inline`s, its `permission`s. |
| `edges` | Directed `{source, target, kind, field, null}`. Every `source` and `target` is a node id in the same document. |

The document carries no user identity, no URLs, no hostnames and no record
data.

## Node ids

| Kind | Id | Example |
| --- | --- | --- |
| `app` | `app:<app_label>` | `app:library` |
| `model` | `model:<app_label>.<model_name>` (lower case) | `model:library.book` |
| `admin` | `admin:<app_label>.<model_name>` | `admin:library.book` |
| `inline` | `inline:<parent label>:<inline model label>` (+ `#2`, `#3` for repeats) | `inline:library.book:library.review` |
| `permission` | `permission:<app_label>.<codename>` | `permission:library.view_book` |

## Nodes

### `app`

| Key | Type | Notes |
| --- | --- | --- |
| `label` | string | `AppConfig.label` |
| `name` | string | `AppConfig.verbose_name` |

### `model`

| Key | Type | Notes |
| --- | --- | --- |
| `app` | id | Its `app` node. |
| `label` | string | `"library.Book"` (`_meta.label`). |
| `object_name`, `verbose_name`, `verbose_name_plural` | string | |
| `pk` | string | Primary key field name. |
| `ordering` | string[] | `Meta.ordering`. |
| `fields` | field[] | Only fields the ModelAdmin exposes (form, read-only, `list_display`) plus the pk. A field excluded from the admin is not listed. |

**field**

| Key | Type | Notes |
| --- | --- | --- |
| `name` | string | |
| `type` | string | `get_internal_type()` — the storage type (`CharField` for an `EmailField`). |
| `field_class` | string | The field class (`EmailField`). |
| `verbose_name`, `help_text` | string | |
| `primary_key`, `null`, `blank`, `editable`, `unique` | bool | From the model field. |
| `readonly` | bool | Read-only *in the admin*: in `readonly_fields`, or not on the form. |
| `max_length` | int \| null | |
| `choices` | `{value, label}[]` | Flattened (option groups expanded). Non-JSON values are stringified. |
| `relation` | relation \| null | Forward relations only. |

**relation**

| Key | Type | Notes |
| --- | --- | --- |
| `kind` | `foreign_key` \| `one_to_one` \| `many_to_many` | |
| `target` | id \| null | `null` when the related model is not in this graph (unregistered, excluded, or invisible to the user). Its name is then not disclosed anywhere. |
| `on_delete` | string \| null | `CASCADE`, `PROTECT`, `SET_NULL`, … |
| `related_name` | string \| null | `null` whenever `target` is `null`. |
| `through` | id \| null | An explicit, visible `through` model. |

### `admin`

| Key | Type | Notes |
| --- | --- | --- |
| `model` | id | The model it administers. |
| `class_name` | string | Dotted path of the ModelAdmin class. |
| `permissions` | `{view, add, change, delete}` | `ModelAdmin.has_*_permission(request)`. |
| `url_names` | object | Reversible URL *names* the user may use: `changelist`, `change`, `history` (view or change), `add`, `delete`. |
| `list_display`, `list_display_links`, `list_editable`, `search_fields`, `ordering` | string[] | Request-aware getters; callables become their `__name__`. |
| `list_filter` | `{field, filter, title, parameter}[]` | `"status"` → `{field: "status", filter: "auto"}`; `("publisher", RelatedOnlyFieldListFilter)` → `filter: "RelatedOnlyFieldListFilter"`; a `SimpleListFilter` → `field: null` plus its `title` and `parameter`. |
| `date_hierarchy` | string \| null | |
| `list_per_page` | int | |
| `fields` | string[] | Change form (empty if the user may not view/change). |
| `add_fields` | string[] | Add form (empty if the user may not add). |
| `fieldsets` | `{name, fields}[]` | Of the change form, else the add form. |
| `readonly_fields`, `autocomplete_fields`, `raw_id_fields` | string[] | |
| `prepopulated_fields` | `{field: string[]}` | |
| `actions` | `{name, description, allowed_permissions}[]` | `get_actions(request)` — only actions the user may run. |
| `inlines` | id[] | `get_inline_instances(request)` — only inlines the user has permission on. |

### `inline`

| Key | Type | Notes |
| --- | --- | --- |
| `admin` | id | The parent `admin` node. |
| `model` | id | The inline's model. It has a `model` node only if it is registered and visible on its own. |
| `class_name` | string | |
| `style` | `tabular` \| `stacked` \| `other` | |
| `permissions` | `{view, add, change, delete}` | The inline's own `has_*_permission`. |
| `fk_name` | string \| null | The FK to the parent. |
| `extra`, `min_num`, `max_num` | int \| null | `get_extra` / `get_min_num` / `get_max_num`. |
| `fields`, `readonly_fields` | string[] | |

### `permission`

| Key | Type | Notes |
| --- | --- | --- |
| `model` | id | |
| `codename`, `name` | string | `view_book`, `Can view book`. |
| `action` | `view` \| `add` \| `change` \| `delete` \| `custom` | `custom` for `Meta.permissions`. |
| `granted` | bool \| null | Built-in actions: the ModelAdmin's `has_<action>_permission`. Custom: always `null` (the admin does not evaluate them). |

## Edges

| Kind | Source → target | Extra |
| --- | --- | --- |
| `contains` | app → model | |
| `foreign_key`, `one_to_one`, `many_to_many` | model → model | `field`, `null` |
| `admin_of` | admin → model, inline → model | |
| `inline_of` | inline → admin | |
| `permission_of` | permission → model | |

## Reading a graph without Django

```python
import json
from django_admin_graph.schema import AdminGraph

graph = AdminGraph.from_dict(json.load(open("graph.json")))
for model in graph.models:
    print(model.label, [f.name for f in model.fields])
```
