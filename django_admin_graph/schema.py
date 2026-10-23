"""The typed graph model — the stable, versioned contract of this package.

Everything :func:`~django_admin_graph.build_graph` returns is an instance of
the frozen dataclasses below. ``AdminGraph.to_dict()`` produces the JSON
document described in ``docs/schema.md`` (and validated by
``django_admin_graph/schema.json``); ``AdminGraph.from_dict()`` reads it back,
so a consumer such as ``django-admin-skills`` can work from a saved file
without importing the Django project that produced it.

Compatibility rule: adding an optional key bumps the *minor* part of
:data:`SCHEMA_VERSION`; renaming or removing a key, or changing a value's
meaning, bumps the *major* part. Consumers should refuse a major version
they do not know and ignore keys they do not recognise.
"""

from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Literal
from typing import cast

SCHEMA_VERSION = "1.0"

NodeKind = Literal["app", "model", "admin", "inline", "permission"]
EdgeKind = Literal[
    "contains",
    "foreign_key",
    "one_to_one",
    "many_to_many",
    "admin_of",
    "inline_of",
    "permission_of",
]
RelationKind = Literal["foreign_key", "one_to_one", "many_to_many"]
ScopeMode = Literal["system", "request"]
PermissionAction = Literal["add", "change", "delete", "view", "custom"]

RELATION_KINDS: tuple[RelationKind, ...] = ("foreign_key", "one_to_one", "many_to_many")


class SchemaVersionError(ValueError):
    """Raised by :meth:`AdminGraph.from_dict` for an unknown major version."""


# --------------------------------------------------------------------------- #
# Leaf value objects
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Choice:
    """One ``(value, label)`` pair of a field's ``choices``."""

    value: Any
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "label": self.label}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Choice:
        return cls(value=data["value"], label=str(data["label"]))


@dataclass(frozen=True, slots=True)
class Relation:
    """The forward side of a relational field.

    ``target`` is the id of the related model node, or ``None`` when the
    related model is not part of this graph (not registered on the site, or
    not visible to the requesting user). The related model's name is never
    disclosed when it is not in the graph.
    """

    kind: RelationKind
    target: str | None
    on_delete: str | None = None
    related_name: str | None = None
    through: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "on_delete": self.on_delete,
            "related_name": self.related_name,
            "through": self.through,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Relation:
        return cls(
            kind=cast(RelationKind, data["kind"]),
            target=data.get("target"),
            on_delete=data.get("on_delete"),
            related_name=data.get("related_name"),
            through=data.get("through"),
        )


@dataclass(frozen=True, slots=True)
class FieldInfo:
    """A model field as the admin exposes it."""

    name: str
    type: str
    verbose_name: str
    field_class: str = ""
    primary_key: bool = False
    null: bool = False
    blank: bool = False
    editable: bool = True
    unique: bool = False
    readonly: bool = False
    max_length: int | None = None
    help_text: str = ""
    choices: tuple[Choice, ...] = ()
    relation: Relation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "field_class": self.field_class,
            "verbose_name": self.verbose_name,
            "primary_key": self.primary_key,
            "null": self.null,
            "blank": self.blank,
            "editable": self.editable,
            "unique": self.unique,
            "readonly": self.readonly,
            "max_length": self.max_length,
            "help_text": self.help_text,
            "choices": [c.to_dict() for c in self.choices],
            "relation": self.relation.to_dict() if self.relation else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FieldInfo:
        relation = data.get("relation")
        return cls(
            name=data["name"],
            type=data["type"],
            verbose_name=data.get("verbose_name", data["name"]),
            field_class=data.get("field_class", data["type"]),
            primary_key=bool(data.get("primary_key", False)),
            null=bool(data.get("null", False)),
            blank=bool(data.get("blank", False)),
            editable=bool(data.get("editable", True)),
            unique=bool(data.get("unique", False)),
            readonly=bool(data.get("readonly", False)),
            max_length=data.get("max_length"),
            help_text=data.get("help_text", ""),
            choices=tuple(Choice.from_dict(c) for c in data.get("choices", ())),
            relation=Relation.from_dict(relation) if relation else None,
        )


@dataclass(frozen=True, slots=True)
class Permissions:
    """The four admin permissions, as answered by ``ModelAdmin.has_*_permission``."""

    view: bool
    add: bool
    change: bool
    delete: bool

    def to_dict(self) -> dict[str, bool]:
        return {"view": self.view, "add": self.add, "change": self.change, "delete": self.delete}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Permissions:
        return cls(
            view=bool(data["view"]),
            add=bool(data["add"]),
            change=bool(data["change"]),
            delete=bool(data["delete"]),
        )


@dataclass(frozen=True, slots=True)
class ActionInfo:
    """A ModelAdmin action the user may run (from ``ModelAdmin.get_actions``)."""

    name: str
    description: str
    allowed_permissions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "allowed_permissions": list(self.allowed_permissions),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ActionInfo:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            allowed_permissions=tuple(data.get("allowed_permissions", ())),
        )


@dataclass(frozen=True, slots=True)
class ListFilterInfo:
    """One ``list_filter`` entry, normalised.

    ``field`` is the model field path for field filters, ``None`` for a
    ``SimpleListFilter``; ``parameter`` is the query-string key a
    ``SimpleListFilter`` reads.
    """

    field: str | None
    filter: str
    title: str | None = None
    parameter: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "filter": self.filter,
            "title": self.title,
            "parameter": self.parameter,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ListFilterInfo:
        return cls(
            field=data.get("field"),
            filter=data["filter"],
            title=data.get("title"),
            parameter=data.get("parameter"),
        )


@dataclass(frozen=True, slots=True)
class Fieldset:
    """One ``fieldsets`` entry: an optional title and its field names."""

    name: str | None
    fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "fields": list(self.fields)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Fieldset:
        return cls(name=data.get("name"), fields=tuple(data.get("fields", ())))


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class AppNode:
    id: str
    label: str
    name: str
    kind: Literal["app"] = "app"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "label": self.label, "name": self.name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppNode:
        return cls(id=data["id"], label=data["label"], name=data.get("name", data["label"]))


@dataclass(frozen=True, slots=True)
class ModelNode:
    id: str
    app: str
    label: str
    object_name: str
    verbose_name: str
    verbose_name_plural: str
    pk: str
    fields: tuple[FieldInfo, ...] = ()
    ordering: tuple[str, ...] = ()
    kind: Literal["model"] = "model"

    def field(self, name: str) -> FieldInfo | None:
        """The field called ``name``, or ``None``."""
        return next((f for f in self.fields if f.name == name), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "app": self.app,
            "label": self.label,
            "object_name": self.object_name,
            "verbose_name": self.verbose_name,
            "verbose_name_plural": self.verbose_name_plural,
            "pk": self.pk,
            "ordering": list(self.ordering),
            "fields": [f.to_dict() for f in self.fields],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelNode:
        return cls(
            id=data["id"],
            app=data["app"],
            label=data["label"],
            object_name=data["object_name"],
            verbose_name=data.get("verbose_name", data["object_name"]),
            verbose_name_plural=data.get("verbose_name_plural", data["object_name"]),
            pk=data["pk"],
            ordering=tuple(data.get("ordering", ())),
            fields=tuple(FieldInfo.from_dict(f) for f in data.get("fields", ())),
        )


@dataclass(frozen=True, slots=True)
class AdminNode:
    """A registered ``ModelAdmin``, resolved for one request."""

    id: str
    model: str
    class_name: str
    permissions: Permissions
    url_names: Mapping[str, str] = field(default_factory=dict)
    list_display: tuple[str, ...] = ()
    list_display_links: tuple[str, ...] = ()
    list_editable: tuple[str, ...] = ()
    list_filter: tuple[ListFilterInfo, ...] = ()
    search_fields: tuple[str, ...] = ()
    ordering: tuple[str, ...] = ()
    date_hierarchy: str | None = None
    list_per_page: int = 100
    fields: tuple[str, ...] = ()
    add_fields: tuple[str, ...] = ()
    fieldsets: tuple[Fieldset, ...] = ()
    readonly_fields: tuple[str, ...] = ()
    autocomplete_fields: tuple[str, ...] = ()
    raw_id_fields: tuple[str, ...] = ()
    prepopulated_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    actions: tuple[ActionInfo, ...] = ()
    inlines: tuple[str, ...] = ()
    kind: Literal["admin"] = "admin"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "model": self.model,
            "class_name": self.class_name,
            "permissions": self.permissions.to_dict(),
            "url_names": dict(self.url_names),
            "list_display": list(self.list_display),
            "list_display_links": list(self.list_display_links),
            "list_editable": list(self.list_editable),
            "list_filter": [f.to_dict() for f in self.list_filter],
            "search_fields": list(self.search_fields),
            "ordering": list(self.ordering),
            "date_hierarchy": self.date_hierarchy,
            "list_per_page": self.list_per_page,
            "fields": list(self.fields),
            "add_fields": list(self.add_fields),
            "fieldsets": [f.to_dict() for f in self.fieldsets],
            "readonly_fields": list(self.readonly_fields),
            "autocomplete_fields": list(self.autocomplete_fields),
            "raw_id_fields": list(self.raw_id_fields),
            "prepopulated_fields": {k: list(v) for k, v in self.prepopulated_fields.items()},
            "actions": [a.to_dict() for a in self.actions],
            "inlines": list(self.inlines),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AdminNode:
        return cls(
            id=data["id"],
            model=data["model"],
            class_name=data["class_name"],
            permissions=Permissions.from_dict(data["permissions"]),
            url_names=dict(data.get("url_names", {})),
            list_display=tuple(data.get("list_display", ())),
            list_display_links=tuple(data.get("list_display_links", ())),
            list_editable=tuple(data.get("list_editable", ())),
            list_filter=tuple(ListFilterInfo.from_dict(f) for f in data.get("list_filter", ())),
            search_fields=tuple(data.get("search_fields", ())),
            ordering=tuple(data.get("ordering", ())),
            date_hierarchy=data.get("date_hierarchy"),
            list_per_page=int(data.get("list_per_page", 100)),
            fields=tuple(data.get("fields", ())),
            add_fields=tuple(data.get("add_fields", ())),
            fieldsets=tuple(Fieldset.from_dict(f) for f in data.get("fieldsets", ())),
            readonly_fields=tuple(data.get("readonly_fields", ())),
            autocomplete_fields=tuple(data.get("autocomplete_fields", ())),
            raw_id_fields=tuple(data.get("raw_id_fields", ())),
            prepopulated_fields={
                k: tuple(v) for k, v in data.get("prepopulated_fields", {}).items()
            },
            actions=tuple(ActionInfo.from_dict(a) for a in data.get("actions", ())),
            inlines=tuple(data.get("inlines", ())),
        )


@dataclass(frozen=True, slots=True)
class InlineNode:
    """An ``InlineModelAdmin`` attached to a ModelAdmin."""

    id: str
    admin: str
    model: str
    class_name: str
    style: Literal["tabular", "stacked", "other"]
    permissions: Permissions
    fk_name: str | None = None
    extra: int = 3
    min_num: int | None = None
    max_num: int | None = None
    fields: tuple[str, ...] = ()
    readonly_fields: tuple[str, ...] = ()
    kind: Literal["inline"] = "inline"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "admin": self.admin,
            "model": self.model,
            "class_name": self.class_name,
            "style": self.style,
            "permissions": self.permissions.to_dict(),
            "fk_name": self.fk_name,
            "extra": self.extra,
            "min_num": self.min_num,
            "max_num": self.max_num,
            "fields": list(self.fields),
            "readonly_fields": list(self.readonly_fields),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> InlineNode:
        return cls(
            id=data["id"],
            admin=data["admin"],
            model=data["model"],
            class_name=data["class_name"],
            style=data.get("style", "other"),
            permissions=Permissions.from_dict(data["permissions"]),
            fk_name=data.get("fk_name"),
            extra=int(data.get("extra", 3)),
            min_num=data.get("min_num"),
            max_num=data.get("max_num"),
            fields=tuple(data.get("fields", ())),
            readonly_fields=tuple(data.get("readonly_fields", ())),
        )


@dataclass(frozen=True, slots=True)
class PermissionNode:
    """A permission declared on a model.

    ``granted`` is the ModelAdmin's answer (``has_<action>_permission``) for the
    four built-in actions and ``None`` for custom ``Meta.permissions`` — the
    admin does not evaluate those, so neither do we.
    """

    id: str
    model: str
    codename: str
    name: str
    action: PermissionAction
    granted: bool | None
    kind: Literal["permission"] = "permission"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "model": self.model,
            "codename": self.codename,
            "name": self.name,
            "action": self.action,
            "granted": self.granted,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PermissionNode:
        return cls(
            id=data["id"],
            model=data["model"],
            codename=data["codename"],
            name=data.get("name", data["codename"]),
            action=data.get("action", "custom"),
            granted=data.get("granted"),
        )


Node = AppNode | ModelNode | AdminNode | InlineNode | PermissionNode

_NODE_TYPES: dict[str, type[AppNode | ModelNode | AdminNode | InlineNode | PermissionNode]] = {
    "app": AppNode,
    "model": ModelNode,
    "admin": AdminNode,
    "inline": InlineNode,
    "permission": PermissionNode,
}


# --------------------------------------------------------------------------- #
# Edges
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Edge:
    """A directed edge. Relation edges carry the field that defines them."""

    source: str
    target: str
    kind: EdgeKind
    field: str | None = None
    null: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "field": self.field,
            "null": self.null,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Edge:
        return cls(
            source=data["source"],
            target=data["target"],
            kind=cast(EdgeKind, data["kind"]),
            field=data.get("field"),
            null=data.get("null"),
        )


# --------------------------------------------------------------------------- #
# The graph
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SiteInfo:
    name: str
    site_header: str
    site_title: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "site_header": self.site_header, "site_title": self.site_title}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SiteInfo:
        return cls(
            name=data["name"],
            site_header=data.get("site_header", ""),
            site_title=data.get("site_title", ""),
        )


@dataclass(frozen=True, slots=True)
class AdminGraph:
    """The admin site as a typed graph. Build it with :func:`build_graph`."""

    site: SiteInfo
    scope: ScopeMode
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    generator_version: str = ""
    schema_version: str = SCHEMA_VERSION

    # -- lookups -------------------------------------------------------- #
    def node(self, node_id: str) -> Node | None:
        """The node with ``node_id``, or ``None``."""
        return next((n for n in self.nodes if n.id == node_id), None)

    def _of(self, cls: type[Any]) -> Iterator[Any]:
        return (n for n in self.nodes if isinstance(n, cls))

    @property
    def apps(self) -> tuple[AppNode, ...]:
        return tuple(self._of(AppNode))

    @property
    def models(self) -> tuple[ModelNode, ...]:
        return tuple(self._of(ModelNode))

    @property
    def admins(self) -> tuple[AdminNode, ...]:
        return tuple(self._of(AdminNode))

    @property
    def inlines(self) -> tuple[InlineNode, ...]:
        return tuple(self._of(InlineNode))

    @property
    def permissions(self) -> tuple[PermissionNode, ...]:
        return tuple(self._of(PermissionNode))

    def model(self, label: str) -> ModelNode | None:
        """The model node for ``"app_label.modelname"`` (case-insensitive)."""
        node = self.node(f"model:{label.lower()}")
        return node if isinstance(node, ModelNode) else None

    def admin_for(self, model_label: str) -> AdminNode | None:
        node = self.node(f"admin:{model_label.lower()}")
        return node if isinstance(node, AdminNode) else None

    def edges_from(self, node_id: str, kind: EdgeKind | None = None) -> tuple[Edge, ...]:
        return tuple(
            e for e in self.edges if e.source == node_id and (kind is None or e.kind == kind)
        )

    def edges_to(self, node_id: str, kind: EdgeKind | None = None) -> tuple[Edge, ...]:
        return tuple(
            e for e in self.edges if e.target == node_id and (kind is None or e.kind == kind)
        )

    def relations(self) -> tuple[Edge, ...]:
        """Every FK / O2O / M2M edge between models in the graph."""
        return tuple(e for e in self.edges if e.kind in RELATION_KINDS)

    # -- (de)serialisation ---------------------------------------------- #
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generator": {"name": "django-admin-graph", "version": self.generator_version},
            "site": self.site.to_dict(),
            "scope": {"mode": self.scope},
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AdminGraph:
        """Rebuild a graph from :meth:`to_dict` output (e.g. a saved JSON file).

        Unknown keys are ignored; an unknown *major* schema version raises
        :class:`SchemaVersionError`.
        """
        version = str(data.get("schema_version", ""))
        if version.split(".")[0] != SCHEMA_VERSION.split(".")[0]:
            raise SchemaVersionError(
                f"Unsupported schema_version {version!r}; this reader understands "
                f"{SCHEMA_VERSION.split('.')[0]}.x"
            )
        nodes: list[Node] = []
        for raw in data.get("nodes", ()):
            node_type = _NODE_TYPES.get(raw.get("kind", ""))
            if node_type is not None:  # forward-compatible: skip unknown kinds
                nodes.append(node_type.from_dict(raw))
        return cls(
            site=SiteInfo.from_dict(data["site"]),
            scope=cast(ScopeMode, data.get("scope", {}).get("mode", "system")),
            nodes=tuple(nodes),
            edges=tuple(Edge.from_dict(e) for e in data.get("edges", ())),
            generator_version=str(data.get("generator", {}).get("version", "")),
            schema_version=version,
        )
