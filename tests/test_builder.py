"""build_graph() in system mode: the whole site, faithfully."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib import admin
from django.test import override_settings

from django_admin_graph import build_graph
from django_admin_graph import to_json
from django_admin_graph.builder import SystemUser
from django_admin_graph.builder import system_request
from django_admin_graph.schema import AdminNode
from django_admin_graph.schema import InlineNode
from django_admin_graph.schema import ModelNode
from tests.helpers import assert_closed

pytestmark = pytest.mark.django_db


@pytest.fixture
def graph() -> Any:
    return build_graph()


def test_scope_and_site(graph: Any) -> None:
    assert graph.scope == "system"
    assert graph.schema_version == "1.0"
    assert graph.site.name == "admin"
    assert graph.generator_version


def test_registered_models_only(graph: Any) -> None:
    labels = {m.label for m in graph.models}
    assert {"library.Book", "library.Author", "auth.User", "auth.Group"} <= labels
    # Chapter is only an inline, AuditEntry is not registered at all.
    assert "library.Chapter" not in labels
    assert "library.AuditEntry" not in labels
    assert "auditentry" not in to_json(graph).lower()


def test_graph_is_closed_and_deterministic(graph: Any) -> None:
    assert_closed(graph)
    assert to_json(graph) == to_json(build_graph())


def test_apps_contain_models(graph: Any) -> None:
    library = graph.node("app:library")
    assert library is not None
    assert library.name == "Library"
    contained = {e.target for e in graph.edges_from("app:library", "contains")}
    assert "model:library.book" in contained
    assert all(isinstance(graph.node(t), ModelNode) for t in contained)


def test_fields_follow_the_model_admin(graph: Any) -> None:
    book = graph.model("library.Book")
    names = [f.name for f in book.fields]
    assert names[0] == "id"
    assert "internal_notes" not in names  # excluded by BookAdmin.exclude
    assert {"title", "slug", "author", "publisher", "tags", "status", "price"} <= set(names)

    status = book.field("status")
    assert status.type == "CharField"
    assert [(c.value, c.label) for c in status.choices] == [
        ("draft", "Draft"),
        ("published", "Published"),
    ]
    assert status.max_length == 20

    created = book.field("created_at")
    assert created.readonly is True
    assert book.field("id").readonly is True
    assert book.field("title").readonly is False

    author = graph.model("library.Author")
    assert author.field("bio").help_text == "Shown on the author page."
    assert author.field("email").field_class == "EmailField"
    assert author.field("email").unique is True
    assert author.ordering == ("name",)


def test_relations(graph: Any) -> None:
    book = graph.model("library.Book")
    fk = book.field("author").relation
    assert fk.kind == "foreign_key"
    assert fk.target == "model:library.author"
    assert fk.on_delete == "PROTECT"
    assert fk.related_name == "books"
    assert book.field("publisher").relation.on_delete == "SET_NULL"
    assert book.field("tags").relation.kind == "many_to_many"
    assert book.field("tags").relation.through is None  # auto-created

    rels = {(e.source, e.field, e.kind, e.null) for e in graph.relations()}
    assert ("model:library.book", "author", "foreign_key", False) in rels
    assert ("model:library.book", "publisher", "foreign_key", True) in rels
    assert ("model:library.book", "tags", "many_to_many", False) in rels
    assert ("model:library.authorprofile", "author", "one_to_one", False) in rels


def test_admin_node(graph: Any) -> None:
    admin_node = graph.admin_for("library.book")
    assert isinstance(admin_node, AdminNode)
    assert admin_node.class_name.endswith("library.admin.BookAdmin")
    assert admin_node.list_display == ("title", "author", "status", "price_display")
    assert admin_node.list_display_links == ("title",)
    assert admin_node.search_fields == ("title", "author__name")
    assert admin_node.readonly_fields == ("created_at",)
    assert admin_node.autocomplete_fields == ("author",)
    assert admin_node.prepopulated_fields == {"slug": ("title",)}
    assert admin_node.date_hierarchy == "created_at"
    assert admin_node.list_per_page == 25
    filters = [(f.field, f.filter, f.title, f.parameter) for f in admin_node.list_filter]
    assert filters == [
        ("status", "auto", None, None),
        ("publisher", "RelatedOnlyFieldListFilter", None, None),
        (None, "PriceFilter", "price band", "band"),
    ]
    actions = {a.name: a for a in admin_node.actions}
    assert actions["mark_published"].description == "Publish selected books"
    assert actions["mark_published"].allowed_permissions == ("publish",)
    assert actions["delete_selected"].description == "Delete selected books"
    assert admin_node.url_names["changelist"] == "admin:library_book_changelist"
    assert set(admin_node.url_names) == {"changelist", "change", "history", "add", "delete"}
    assert graph.edges_from(admin_node.id, "admin_of")[0].target == "model:library.book"


def test_fieldsets(graph: Any) -> None:
    review_admin = graph.admin_for("library.review")
    assert [(f.name, f.fields) for f in review_admin.fieldsets] == [
        (None, ("book", "rating")),
        ("Text", ("body",)),
    ]
    assert review_admin.fields == ("book", "rating", "body")


def test_inlines(graph: Any) -> None:
    admin_node = graph.admin_for("library.book")
    assert admin_node.inlines == (
        "inline:library.book:library.review",
        "inline:library.book:library.chapter",
    )
    review = graph.node("inline:library.book:library.review")
    chapter = graph.node("inline:library.book:library.chapter")
    assert isinstance(review, InlineNode)
    assert review.style == "tabular"
    assert review.fk_name == "book"
    assert review.extra == 1
    assert chapter.style == "stacked"
    assert chapter.max_num == 50
    assert "title" in chapter.fields
    assert {e.target for e in graph.edges_from(review.id)} == {
        "admin:library.book",
        "model:library.review",
    }
    # Chapter is not registered: the inline is there, the model node is not.
    assert {e.target for e in graph.edges_from(chapter.id)} == {"admin:library.book"}


def test_node_order_groups_each_model(graph: Any) -> None:
    ids = [n.id for n in graph.nodes]
    i = ids.index("model:library.book")
    assert ids[i + 1] == "admin:library.book"
    assert ids[i + 2].startswith("inline:library.book:")


def test_permissions(graph: Any) -> None:
    perms = {p.codename: p for p in graph.permissions if p.model == "model:library.book"}
    assert set(perms) == {"add_book", "change_book", "delete_book", "view_book", "publish_book"}
    assert perms["view_book"].granted is True
    assert perms["publish_book"].action == "custom"
    assert perms["publish_book"].granted is None
    assert perms["publish_book"].name == "Can publish book"
    # The ModelAdmin's own answer wins, even for the system user.
    publisher = graph.admin_for("library.publisher")
    assert publisher.permissions.add is False
    assert "add" not in publisher.url_names
    add_pub = graph.node("permission:library.add_publisher")
    assert add_pub.granted is False
    assert graph.edges_from(add_pub.id, "permission_of")[0].target == "model:library.publisher"


def test_app_labels_filter() -> None:
    graph = build_graph(app_labels=["auth"])
    assert {a.label for a in graph.apps} == {"auth"}
    assert all(m.app == "app:auth" for m in graph.models)


def test_relations_within_one_app() -> None:
    graph = build_graph(app_labels=["auth"])
    assert_closed(graph)
    user = graph.model("auth.User")
    groups = user.field("groups").relation
    assert groups.target == "model:auth.group"


@override_settings(DJANGO_ADMIN_GRAPH={"EXCLUDE_APPS": ["auth"]})
def test_exclude_apps() -> None:
    graph = build_graph()
    assert "app:auth" not in {a.id for a in graph.apps}


@override_settings(DJANGO_ADMIN_GRAPH={"EXCLUDE_MODELS": ["library.Author"]})
def test_exclude_models_hides_relation_targets() -> None:
    graph = build_graph()
    assert graph.model("library.author") is None
    relation = graph.model("library.book").field("author").relation
    assert relation.target is None
    assert relation.related_name is None
    assert '"model:library.author"' not in to_json(graph)
    assert_closed(graph)


def test_custom_site() -> None:
    from tests.test_project.library.admin import ops_site

    graph = build_graph(ops_site)
    assert graph.site.name == "ops"
    assert graph.site.site_header == "Ops"
    assert [m.label for m in graph.models] == ["library.Tag"]
    assert graph.admin_for("library.tag").url_names["changelist"] == "ops:library_tag_changelist"


def test_empty_site() -> None:
    graph = build_graph(admin.AdminSite(name="empty"))
    assert graph.nodes == ()
    assert graph.edges == ()


def test_system_user_is_unsaved_superuser() -> None:
    request = system_request()
    user = request.user
    assert isinstance(user, SystemUser)
    assert user.pk is None
    assert user.has_perm("anything") and user.has_perms(["a", "b"])
    assert user.has_module_perms("library")
    assert str(user) == user.get_username() == "django-admin-graph"
    assert request.method == "GET"
