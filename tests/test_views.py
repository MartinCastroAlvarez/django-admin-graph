"""The optional JSON view: staff-only, read-only, per-user, never cached."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import override_settings

from django_admin_graph import AdminGraph

pytestmark = pytest.mark.django_db

URL = "/admin-graph/"


def test_anonymous_gets_401(client_for: Any) -> None:
    response = client_for(None).get(URL)
    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required."}
    assert "no-store" in response["Cache-Control"]


def test_non_staff_gets_403(client_for: Any, non_staff: Any) -> None:
    response = client_for(non_staff).get(URL)
    assert response.status_code == 403
    assert "nodes" not in response.json()


def test_inactive_staff_cannot_log_in(client_for: Any, inactive_staff: Any) -> None:
    # force_login + an inactive user: Django's auth middleware drops them.
    assert client_for(inactive_staff).get(URL).status_code in (401, 403)


def test_limited_staff_gets_filtered_graph(client_for: Any, limited_staff: Any) -> None:
    response = client_for(limited_staff).get(URL)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    cache = response["Cache-Control"]
    assert "private" in cache and "no-store" in cache
    assert "Cookie" in response["Vary"]
    graph = AdminGraph.from_dict(response.json())
    assert graph.scope == "request"
    assert [m.id for m in graph.models] == ["model:library.book"]


def test_app_query_parameter(client_for: Any, superuser: Any) -> None:
    data = client_for(superuser).get(URL, {"app": "auth"}).json()
    assert {n["id"] for n in data["nodes"] if n["kind"] == "app"} == {"app:auth"}


def test_head_is_allowed(client_for: Any, superuser: Any) -> None:
    assert client_for(superuser).head(URL).status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_writes_are_refused(client_for: Any, superuser: Any, method: str) -> None:
    client = client_for(superuser)
    assert getattr(client, method)(URL).status_code == 405


@override_settings(DJANGO_ADMIN_GRAPH={"ADMIN_SITE": "tests.test_project.library.admin.ops_site"})
def test_view_uses_configured_site(client_for: Any, superuser: Any, editor_staff: Any) -> None:
    data = client_for(superuser).get(URL).json()
    assert data["site"]["name"] == "ops"
    # OpsSite.has_permission requires a superuser.
    assert client_for(editor_staff).get(URL).status_code == 403


def test_response_is_valid_json_document(client_for: Any, superuser: Any) -> None:
    body = client_for(superuser).get(URL).content.decode()
    assert json.loads(body)["schema_version"] == "1.0"
