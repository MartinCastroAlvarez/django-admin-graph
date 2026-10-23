"""The graph never shows a user more than the admin would.

Tiers covered: anonymous, non-staff, inactive staff, staff with no model
permissions, staff limited to viewing one model, an editor, a superuser.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied

from django_admin_graph import NotAuthenticated
from django_admin_graph import build_graph
from tests.helpers import assert_closed
from tests.helpers import dumped

pytestmark = pytest.mark.django_db

PACKAGE = Path(__file__).resolve().parent.parent / "django_admin_graph"


def test_anonymous_is_rejected(request_for: Any) -> None:
    with pytest.raises(NotAuthenticated):
        build_graph(request=request_for(None))


def test_request_without_user_is_rejected(rf: Any) -> None:
    with pytest.raises(NotAuthenticated):
        build_graph(request=rf.get("/"))


def test_non_staff_is_rejected_even_with_model_perms(request_for: Any, non_staff: Any) -> None:
    with pytest.raises(PermissionDenied):
        build_graph(request=request_for(non_staff))


def test_inactive_staff_is_rejected(request_for: Any, inactive_staff: Any) -> None:
    with pytest.raises(PermissionDenied):
        build_graph(request=request_for(inactive_staff))


def test_site_has_permission_override_is_respected(request_for: Any, editor_staff: Any) -> None:
    from tests.test_project.library.admin import ops_site

    with pytest.raises(PermissionDenied):
        build_graph(ops_site, request_for(editor_staff))


def test_staff_without_permissions_sees_nothing(request_for: Any, staff_no_perms: Any) -> None:
    graph = build_graph(request=request_for(staff_no_perms))
    assert graph.scope == "request"
    assert graph.nodes == ()
    assert graph.edges == ()


def test_limited_staff_sees_only_what_they_may_view(request_for: Any, limited_staff: Any) -> None:
    graph = build_graph(request=request_for(limited_staff))
    assert_closed(graph)
    assert [a.id for a in graph.apps] == ["app:library"]
    assert [m.id for m in graph.models] == ["model:library.book"]

    book = graph.model("library.book")
    # Related models they cannot view are not named anywhere.
    for name in ("author", "publisher", "tags"):
        relation = book.field(name).relation
        assert relation.target is None
        assert relation.related_name is None
    assert graph.relations() == ()
    text = dumped(graph).lower()
    for hidden in ("library.author", "library.publisher", "library.tag", "auth.user"):
        assert hidden not in text, hidden
    assert "internal_notes" not in text

    admin_node = graph.admin_for("library.book")
    assert admin_node.permissions.to_dict() == {
        "view": True,
        "add": False,
        "change": False,
        "delete": False,
    }
    assert set(admin_node.url_names) == {"changelist", "change", "history"}
    # delete_selected needs delete, mark_published needs publish.
    assert admin_node.actions == ()
    # Inlines on models they have no permission on are dropped by the admin.
    assert admin_node.inlines == ()
    assert graph.inlines == ()

    granted = {p.codename: p.granted for p in graph.permissions}
    assert granted == {
        "add_book": False,
        "change_book": False,
        "delete_book": False,
        "view_book": True,
        "publish_book": None,
    }


def test_editor_sees_permitted_actions_and_models(request_for: Any, editor_staff: Any) -> None:
    graph = build_graph(request=request_for(editor_staff))
    assert_closed(graph)
    assert {m.id for m in graph.models} == {"model:library.book", "model:library.author"}
    book = graph.model("library.book")
    assert book.field("author").relation.target == "model:library.author"
    assert book.field("publisher").relation.target is None
    admin_node = graph.admin_for("library.book")
    assert [a.name for a in admin_node.actions] == ["mark_published"]
    assert admin_node.permissions.change is True
    assert admin_node.permissions.delete is False


def test_superuser_matches_system_mode(request_for: Any, superuser: Any) -> None:
    as_root = build_graph(request=request_for(superuser)).to_dict()
    as_system = build_graph().to_dict()
    assert as_root["nodes"] == as_system["nodes"]
    assert as_root["edges"] == as_system["edges"]
    assert as_root["scope"] == {"mode": "request"}


def test_graph_carries_no_user_identity(request_for: Any, editor_staff: Any) -> None:
    text = dumped(build_graph(request=request_for(editor_staff)))
    assert "editor" not in text
    assert "@" not in text  # no emails, no addresses


def test_no_record_data_is_ever_read(
    request_for: Any, superuser: Any, django_assert_max_num_queries: Any
) -> None:
    # The builder reads metadata only. The one query budget we allow is the
    # auth backend loading the user's permissions; no model rows are fetched.
    from tests.test_project.library.models import Author

    Author.objects.create(name="Secret Name", email="secret@example.com")
    user = request_for(superuser)
    with django_assert_max_num_queries(0):
        graph = build_graph(request=user)
    assert "Secret Name" not in dumped(graph)


def test_package_source_has_no_dangerous_constructs() -> None:
    banned = re.compile(
        r"csrf_exempt|mark_safe|\beval\(|\bexec\(|pickle|yaml\.load|shell=True|\.raw\(|"
        r"\.extra\(|has_perm\(|objects\.(all|filter|get)\("
    )
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if banned.search(code) and "def has_perm" not in code:
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert offenders == []
