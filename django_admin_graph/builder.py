"""Build an :class:`~django_admin_graph.schema.AdminGraph` from an ``AdminSite``.

The prime directive: **this module never decides a permission.** Every
visibility question is put to the admin itself —

* ``AdminSite.has_permission(request)`` gates the whole graph,
* ``ModelAdmin.has_module_permission`` + ``ModelAdmin.get_model_perms``
  decide whether a model appears (the same rule the admin index uses),
* ``ModelAdmin.get_actions`` / ``get_inline_instances`` / ``get_fields`` /
  ``get_list_display`` / … decide what appears inside it.

With ``request=None`` the graph is built for a synthetic, unsaved *system*
user that every ``has_perm`` check answers ``True`` for — the shape the site
has for an active superuser. That mode is for offline tooling (the
``admin_graph`` management command, code generators); it is never reachable
over HTTP.
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
from collections.abc import Iterable
from collections.abc import Sequence
from typing import Any

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.admin import ModelAdmin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.admin.utils import model_format_dict
from django.contrib.auth import get_permission_codename
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import HttpRequest
from django.utils.encoding import force_str

from django_admin_graph import conf
from django_admin_graph.schema import ActionInfo
from django_admin_graph.schema import AdminGraph
from django_admin_graph.schema import AdminNode
from django_admin_graph.schema import AppNode
from django_admin_graph.schema import Choice
from django_admin_graph.schema import Edge
from django_admin_graph.schema import FieldInfo
from django_admin_graph.schema import Fieldset
from django_admin_graph.schema import InlineNode
from django_admin_graph.schema import ListFilterInfo
from django_admin_graph.schema import ModelNode
from django_admin_graph.schema import Node
from django_admin_graph.schema import PermissionAction
from django_admin_graph.schema import PermissionNode
from django_admin_graph.schema import Permissions
from django_admin_graph.schema import Relation
from django_admin_graph.schema import RelationKind
from django_admin_graph.schema import ScopeMode
from django_admin_graph.schema import SiteInfo

BUILTIN_ACTIONS: tuple[PermissionAction, ...] = ("view", "add", "change", "delete")
_BUILTIN: dict[str, PermissionAction] = {a: a for a in BUILTIN_ACTIONS}


_logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, slots=True)
class _FormShape:
    fields: tuple[str, ...]
    add_fields: tuple[str, ...]
    readonly: tuple[str, ...]
    fieldsets: tuple[Fieldset, ...]


class NotAuthenticated(PermissionDenied):
    """The request carries no authenticated user (maps to HTTP 401)."""


class SystemUser:
    """The unsaved stand-in user for ``request=None`` (offline) builds.

    It is not a database row and cannot log in; it only exists so the
    ModelAdmin's request-aware hooks can be called without a real request.
    """

    pk = None
    id = None
    username = "django-admin-graph"
    is_active = True
    is_staff = True
    is_superuser = True
    is_authenticated = True
    is_anonymous = False

    def get_username(self) -> str:
        return self.username

    def has_perm(self, perm: str, obj: object = None) -> bool:
        return True

    def has_perms(self, perm_list: Iterable[str], obj: object = None) -> bool:
        return True

    def has_module_perms(self, app_label: str) -> bool:
        return True

    def __str__(self) -> str:
        return self.username


def system_request() -> HttpRequest:
    """A bare GET request carrying a :class:`SystemUser`."""
    request = HttpRequest()
    request.method = "GET"
    request.path = "/"
    request.META["SERVER_NAME"] = "localhost"
    request.META["SERVER_PORT"] = "80"
    request.user = SystemUser()  # type: ignore[assignment]
    return request


def check_access(site: AdminSite, request: HttpRequest) -> None:
    """Raise unless ``request`` may see ``site`` at all.

    Delegates to ``AdminSite.has_permission`` (active + staff by default, or
    whatever the site overrides it to).
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        raise NotAuthenticated("Authentication required.")
    if not site.has_permission(request):
        raise PermissionDenied("Staff access required.")


# --------------------------------------------------------------------------- #
# Small normalisers
# --------------------------------------------------------------------------- #
def _name(item: Any) -> str:
    """A stable string name for a list_display / ordering / field entry."""
    if isinstance(item, str):
        return item
    for attr in ("__name__", "name"):
        value = getattr(item, attr, None)
        if isinstance(value, str):
            return value
    return force_str(item)


def _names(items: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(_name(i) for i in (items or ()))


def _json_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return force_str(value)


def _flatten_fields(fields: Iterable[Any]) -> tuple[str, ...]:
    """Flatten ``fields`` entries, which may group names on one line as tuples."""
    out: list[str] = []
    for item in fields:
        if isinstance(item, list | tuple):
            out.extend(_name(i) for i in item)
        else:
            out.append(_name(item))
    return tuple(out)


def _model_id(model: type[models.Model]) -> str:
    return f"model:{model._meta.label_lower}"


def _list_filter(entry: Any) -> ListFilterInfo:
    if isinstance(entry, str):
        return ListFilterInfo(field=entry, filter="auto")
    if isinstance(entry, list | tuple) and len(entry) == 2:
        field_path, filter_cls = entry
        return ListFilterInfo(field=_name(field_path), filter=_name(filter_cls))
    title = getattr(entry, "title", None)
    parameter = getattr(entry, "parameter_name", None)
    return ListFilterInfo(
        field=None,
        filter=_name(entry),
        title=force_str(title) if title is not None else None,
        parameter=force_str(parameter) if parameter is not None else None,
    )


def _action_parts(entry: Any) -> tuple[Any, Any]:
    """``(func, description)`` from a ``get_actions`` value.

    Django 6.1 returns ``Action`` objects (tuple unpacking is deprecated);
    earlier versions return ``(func, name, description)`` tuples.
    """
    if hasattr(entry, "func") and hasattr(entry, "description"):
        return entry.func, entry.description
    func, _name, description = entry
    return func, description


def _permissions(perms: dict[str, bool]) -> Permissions:
    return Permissions(
        view=bool(perms.get("view")),
        add=bool(perms.get("add")),
        change=bool(perms.get("change")),
        delete=bool(perms.get("delete")),
    )


def _class_path(obj: object) -> str:
    cls = type(obj)
    return f"{cls.__module__}.{cls.__qualname__}"


# --------------------------------------------------------------------------- #
# The builder
# --------------------------------------------------------------------------- #
class _Builder:
    def __init__(self, site: AdminSite, request: HttpRequest, app_labels: frozenset[str] | None):
        self.site = site
        self.request = request
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []
        excluded_apps = conf.excluded_apps()
        excluded_models = conf.excluded_models()

        # Pass 1 — which models does the admin show this request? Same rule as
        # the admin index: module permission and at least one model permission.
        self.visible: dict[type[models.Model], tuple[ModelAdmin[Any], dict[str, bool]]] = {}
        # ``_registry`` is the documented-in-practice registry every AdminSite
        # uses; there is no public iterator on Django 4.2.
        registry = sorted(self.site._registry.items(), key=lambda kv: kv[0]._meta.label_lower)
        for model, model_admin in registry:
            opts = model._meta
            if opts.app_label in excluded_apps or opts.label_lower in excluded_models:
                continue
            if app_labels is not None and opts.app_label not in app_labels:
                continue
            if not model_admin.has_module_permission(request):
                continue
            perms = model_admin.get_model_perms(request)
            if True not in perms.values():
                continue
            self.visible[model] = (model_admin, perms)

    def build(self) -> list[Node]:
        apps_seen: dict[str, AppNode] = {}
        for model in self.visible:
            opts = model._meta
            if opts.app_label not in apps_seen:
                apps_seen[opts.app_label] = AppNode(
                    id=f"app:{opts.app_label}",
                    label=opts.app_label,
                    name=force_str(opts.app_config.verbose_name),
                )
        self.nodes.extend(apps_seen[label] for label in sorted(apps_seen))

        for model, (model_admin, perms) in self.visible.items():
            self._model(model, model_admin, perms)
        return self.nodes

    # -- one registered model ------------------------------------------ #
    def _model(
        self, model: type[models.Model], model_admin: ModelAdmin[Any], perms: dict[str, bool]
    ) -> None:
        opts = model._meta
        request = self.request
        model_id = _model_id(model)
        admin_id = f"admin:{opts.label_lower}"

        shape = self._form_shape(model, model_admin, perms)
        form_fields = (*shape.fields, *(f for f in shape.add_fields if f not in shape.fields))
        readonly = shape.readonly
        list_display = _names(model_admin.get_list_display(request))
        exposed = {*form_fields, *readonly, *list_display}

        fields: list[FieldInfo] = []
        for f in [*opts.concrete_fields, *opts.many_to_many]:
            if not (f.primary_key or f.name in exposed):
                continue  # not shown by this ModelAdmin -> not disclosed
            info = self._field(f, form_fields, readonly)
            fields.append(info)
            if info.relation is not None and info.relation.target is not None:
                self.edges.append(
                    Edge(
                        source=model_id,
                        target=info.relation.target,
                        kind=info.relation.kind,
                        field=f.name,
                        null=bool(f.null),
                    )
                )

        assert opts.pk is not None  # noqa: S101 — every concrete model has one
        self.nodes.append(
            ModelNode(
                id=model_id,
                app=f"app:{opts.app_label}",
                label=opts.label,
                object_name=opts.object_name or model.__name__,
                verbose_name=force_str(opts.verbose_name),
                verbose_name_plural=force_str(opts.verbose_name_plural),
                pk=opts.pk.name,
                ordering=_names(opts.ordering),
                fields=tuple(fields),
            )
        )
        self.edges.append(Edge(source=f"app:{opts.app_label}", target=model_id, kind="contains"))

        inline_nodes, inline_edges = self._inlines(model, model_admin, admin_id)
        inline_ids = [n.id for n in inline_nodes]
        admin_node = self._admin(model, model_admin, perms, admin_id, shape, list_display)
        self.nodes.append(dataclasses.replace(admin_node, inlines=tuple(inline_ids)))
        self.edges.append(Edge(source=admin_id, target=model_id, kind="admin_of"))
        self.nodes.extend(inline_nodes)
        self.edges.extend(inline_edges)
        self._permissions(model, perms, model_id)

    def _form_shape(
        self, model: type[models.Model], model_admin: ModelAdmin[Any], perms: dict[str, bool]
    ) -> _FormShape:
        """The change form (if the user may view/change) and add form (if they may add).

        The change form is resolved against an unsaved placeholder instance so
        admins that switch on ``obj`` (``UserAdmin``'s ``add_fieldsets``) show
        their real change form. The placeholder is never saved or queried.
        """
        request = self.request

        def resolve(obj: models.Model | None) -> tuple[Any, Any, Any]:
            return (
                _flatten_fields(model_admin.get_fields(request, obj)),
                _names(model_admin.get_readonly_fields(request, obj)),
                tuple(
                    Fieldset(
                        name=force_str(title) if title is not None else None,
                        fields=_flatten_fields(options.get("fields", ())),
                    )
                    for title, options in model_admin.get_fieldsets(request, obj)
                ),
            )

        fields: tuple[str, ...] = ()
        readonly: tuple[str, ...] = ()
        fieldsets: tuple[Fieldset, ...] = ()
        add_fields: tuple[str, ...] = ()
        if perms.get("view") or perms.get("change"):
            try:
                fields, readonly, fieldsets = resolve(model())
            except Exception:  # third-party admin code that needs a saved object
                _logger.debug("change form needs a saved %s; using add form", model._meta.label)
                fields, readonly, fieldsets = resolve(None)
        if perms.get("add"):
            add_fields, add_readonly, add_fieldsets = resolve(None)
            if not fields:
                readonly, fieldsets = add_readonly, add_fieldsets
        return _FormShape(fields, add_fields, readonly, fieldsets)

    def _field(self, f: Any, form_fields: Sequence[str], readonly: Sequence[str]) -> FieldInfo:
        relation: Relation | None = None
        if f.is_relation and f.related_model is not None:
            kind: RelationKind
            if f.many_to_many:
                kind = "many_to_many"
            elif f.one_to_one:
                kind = "one_to_one"
            else:
                kind = "foreign_key"
            related = f.related_model
            target = _model_id(related) if related in self.visible else None
            remote = f.remote_field
            on_delete = getattr(remote, "on_delete", None)
            through: str | None = None
            if f.many_to_many:
                through_model = getattr(remote, "through", None)
                if (
                    through_model is not None
                    and not through_model._meta.auto_created
                    and through_model in self.visible
                ):
                    through = _model_id(through_model)
            related_name = getattr(remote, "related_name", None)
            relation = Relation(
                kind=kind,
                target=target,
                on_delete=on_delete.__name__ if on_delete is not None else None,
                related_name=related_name if target is not None else None,
                through=through,
            )
        choices = tuple(
            Choice(value=_json_scalar(value), label=force_str(label))
            for value, label in (f.flatchoices or ())
        )
        max_length = getattr(f, "max_length", None)
        return FieldInfo(
            name=f.name,
            type=f.get_internal_type(),
            field_class=type(f).__name__,
            verbose_name=force_str(f.verbose_name),
            primary_key=bool(f.primary_key),
            null=bool(f.null),
            blank=bool(f.blank),
            editable=bool(f.editable),
            unique=bool(f.unique),
            # Read-only *in the admin*: declared read-only, or not on the form.
            readonly=f.name in readonly or f.name not in form_fields,
            max_length=max_length if isinstance(max_length, int) else None,
            help_text=force_str(f.help_text or ""),
            choices=choices,
            relation=relation,
        )

    def _admin(
        self,
        model: type[models.Model],
        model_admin: ModelAdmin[Any],
        perms: dict[str, bool],
        admin_id: str,
        shape: _FormShape,
        list_display: tuple[str, ...],
    ) -> AdminNode:
        request = self.request
        opts = model._meta
        info = (opts.app_label, opts.model_name)
        prefix = f"{self.site.name}:{info[0]}_{info[1]}"
        can_see = perms.get("view") or perms.get("change")
        url_names: dict[str, str] = {}
        if can_see:
            url_names["changelist"] = f"{prefix}_changelist"
            url_names["change"] = f"{prefix}_change"
            url_names["history"] = f"{prefix}_history"
        if perms.get("add"):
            url_names["add"] = f"{prefix}_add"
        if perms.get("delete"):
            url_names["delete"] = f"{prefix}_delete"

        fmt = model_format_dict(opts)
        actions: list[ActionInfo] = []
        for name, entry in model_admin.get_actions(request).items():
            func, description = _action_parts(entry)
            text = force_str(description)
            with contextlib.suppress(TypeError, KeyError, ValueError):
                text = text % fmt  # the admin formats descriptions the same way
            actions.append(
                ActionInfo(
                    name=name,
                    description=text,
                    allowed_permissions=_names(getattr(func, "allowed_permissions", ())),
                )
            )

        links = model_admin.get_list_display_links(request, list(list_display))
        return AdminNode(
            id=admin_id,
            model=_model_id(model),
            class_name=_class_path(model_admin),
            permissions=_permissions(perms),
            url_names=url_names,
            list_display=list_display,
            list_display_links=_names(links),
            list_editable=_names(model_admin.list_editable),
            list_filter=tuple(_list_filter(e) for e in model_admin.get_list_filter(request)),
            search_fields=_names(model_admin.get_search_fields(request)),
            ordering=_names(model_admin.get_ordering(request)),
            date_hierarchy=model_admin.date_hierarchy or None,
            list_per_page=int(model_admin.list_per_page),
            fields=shape.fields,
            add_fields=shape.add_fields,
            fieldsets=shape.fieldsets,
            readonly_fields=shape.readonly,
            autocomplete_fields=_names(model_admin.get_autocomplete_fields(request)),
            raw_id_fields=_names(model_admin.raw_id_fields),
            prepopulated_fields={
                k: _names(v) for k, v in model_admin.get_prepopulated_fields(request).items()
            },
            actions=tuple(actions),
        )

    def _inlines(
        self, model: type[models.Model], model_admin: ModelAdmin[Any], admin_id: str
    ) -> tuple[list[InlineNode], list[Edge]]:
        request = self.request
        nodes: list[InlineNode] = []
        edges: list[Edge] = []
        ids: set[str] = set()
        # get_inline_instances already drops inlines the user has no permission on.
        for inline in model_admin.get_inline_instances(request, None):
            inline_model = inline.model
            base_id = f"inline:{model._meta.label_lower}:{inline_model._meta.label_lower}"
            inline_id, n = base_id, 2
            while inline_id in ids:
                inline_id, n = f"{base_id}#{n}", n + 1
            ids.add(inline_id)
            nodes.append(self._inline(inline, model, admin_id, inline_id))
            edges.append(Edge(source=inline_id, target=admin_id, kind="inline_of"))
            if inline_model in self.visible:
                edges.append(
                    Edge(source=inline_id, target=_model_id(inline_model), kind="admin_of")
                )
        return nodes, edges

    def _inline(
        self,
        inline: InlineModelAdmin[Any, Any],
        parent: type[models.Model],
        admin_id: str,
        inline_id: str,
    ) -> InlineNode:
        request = self.request
        style: Any = "other"
        if isinstance(inline, admin.TabularInline):
            style = "tabular"
        elif isinstance(inline, admin.StackedInline):
            style = "stacked"
        fk_name = inline.fk_name or next(
            (
                f.name
                for f in inline.model._meta.fields
                if f.is_relation and f.related_model is parent
            ),
            None,
        )
        return InlineNode(
            id=inline_id,
            admin=admin_id,
            model=_model_id(inline.model),
            class_name=_class_path(inline),
            style=style,
            permissions=Permissions(
                view=bool(inline.has_view_permission(request, None)),
                add=bool(inline.has_add_permission(request, None)),
                change=bool(inline.has_change_permission(request, None)),
                delete=bool(inline.has_delete_permission(request, None)),
            ),
            fk_name=fk_name,
            extra=int(inline.get_extra(request)),
            min_num=inline.get_min_num(request),
            max_num=inline.get_max_num(request),
            fields=_flatten_fields(inline.get_fields(request)),
            readonly_fields=_names(inline.get_readonly_fields(request)),
        )

    def _permissions(
        self, model: type[models.Model], perms: dict[str, bool], model_id: str
    ) -> None:
        opts = model._meta
        declared: list[tuple[str, str, PermissionAction]] = []
        for action in opts.default_permissions:
            codename = get_permission_codename(action, opts)
            name = f"Can {action} {opts.verbose_name_raw}"
            kind: PermissionAction = _BUILTIN.get(action, "custom")
            declared.append((codename, name, kind))
        for codename, name in opts.permissions:
            declared.append((codename, force_str(name), "custom"))
        for codename, name, action in declared:
            granted = bool(perms.get(action)) if action != "custom" else None
            perm_id = f"permission:{opts.app_label}.{codename}"
            self.nodes.append(
                PermissionNode(
                    id=perm_id,
                    model=model_id,
                    codename=codename,
                    name=name,
                    action=action,
                    granted=granted,
                )
            )
            self.edges.append(Edge(source=perm_id, target=model_id, kind="permission_of"))


def build_graph(
    site: AdminSite | None = None,
    request: HttpRequest | None = None,
    *,
    app_labels: Iterable[str] | None = None,
) -> AdminGraph:
    """Introspect ``site`` into an :class:`AdminGraph`.

    :param site: the ``AdminSite`` to read; defaults to the ``ADMIN_SITE``
        setting (``django.contrib.admin.site``).
    :param request: when given, the graph contains only what this request's
        user can see in the admin, and :class:`NotAuthenticated` /
        ``PermissionDenied`` is raised if they cannot use the site at all.
        When ``None``, the graph is built for an unrestricted system user
        (offline tooling only — never pass ``None`` from a view).
    :param app_labels: restrict the graph to these app labels.
    """
    from django_admin_graph import __version__

    site = site if site is not None else conf.get_admin_site()
    scope: ScopeMode
    if request is None:
        scope = "system"
        request = system_request()
    else:
        check_access(site, request)
        scope = "request"
    labels = frozenset(app_labels) if app_labels is not None else None
    builder = _Builder(site, request, labels)
    nodes = builder.build()
    return AdminGraph(
        site=SiteInfo(
            name=site.name,
            site_header=force_str(site.site_header),
            site_title=force_str(site.site_title),
        ),
        scope=scope,
        nodes=tuple(nodes),
        edges=tuple(builder.edges),
        generator_version=__version__,
    )
