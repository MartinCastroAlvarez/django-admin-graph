"""The JSON contract: JSON Schema validity, round-trips, versioning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from django_admin_graph import SCHEMA_VERSION
from django_admin_graph import AdminGraph
from django_admin_graph import SchemaVersionError
from django_admin_graph import build_graph
from django_admin_graph import to_json

pytestmark = pytest.mark.django_db

SCHEMA = json.loads(
    (Path(__file__).resolve().parent.parent / "django_admin_graph" / "schema.json").read_text()
)


def test_system_graph_validates_against_json_schema() -> None:
    jsonschema.validate(json.loads(to_json(build_graph())), SCHEMA)


def test_request_graph_validates_against_json_schema(request_for: Any, editor_staff: Any) -> None:
    graph = build_graph(request=request_for(editor_staff))
    jsonschema.validate(graph.to_dict(), SCHEMA)


def test_round_trip_is_lossless() -> None:
    graph = build_graph()
    again = AdminGraph.from_dict(json.loads(to_json(graph)))
    assert again == graph
    assert to_json(again) == to_json(graph)


def test_minor_versions_are_read_and_unknown_keys_ignored() -> None:
    data = build_graph().to_dict()
    data["schema_version"] = "1.99"
    data["future_key"] = {"anything": True}
    data["nodes"].append({"id": "widget:x", "kind": "widget"})
    data["nodes"][0]["extra"] = 1
    graph = AdminGraph.from_dict(data)
    assert graph.schema_version == "1.99"
    assert graph.node("widget:x") is None


@pytest.mark.parametrize("version", ["2.0", "0.1", ""])
def test_unknown_major_version_is_refused(version: str) -> None:
    data = build_graph().to_dict()
    data["schema_version"] = version
    with pytest.raises(SchemaVersionError):
        AdminGraph.from_dict(data)


def test_minimal_document_uses_defaults() -> None:
    graph = AdminGraph.from_dict(
        {
            "schema_version": SCHEMA_VERSION,
            "site": {"name": "admin"},
            "nodes": [
                {"id": "app:a", "kind": "app", "label": "a"},
                {
                    "id": "model:a.b",
                    "kind": "model",
                    "app": "app:a",
                    "label": "a.B",
                    "object_name": "B",
                    "pk": "id",
                    "fields": [{"name": "id", "type": "AutoField"}],
                },
                {
                    "id": "permission:a.x",
                    "kind": "permission",
                    "model": "model:a.b",
                    "codename": "x",
                },
            ],
        }
    )
    assert graph.scope == "system"
    assert graph.apps[0].name == "a"
    model = graph.model("a.b")
    assert model is not None
    assert model.verbose_name == "B"
    assert model.fields[0].field_class == "AutoField"
    assert graph.permissions[0].action == "custom"
    assert graph.permissions[0].granted is None


def test_lookups() -> None:
    graph = build_graph()
    assert graph.model("LIBRARY.BOOK") is graph.model("library.book")
    assert graph.model("library.nope") is None
    assert graph.admin_for("library.nope") is None
    assert graph.model("library.book").field("nope") is None
    assert graph.edges_to("model:library.book", "admin_of")[0].source == "admin:library.book"
    assert len(graph.edges_to("model:library.book")) > 1
    assert graph.node("admin:library.book") in graph.admins
