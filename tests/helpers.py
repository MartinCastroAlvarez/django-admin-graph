"""Assertions shared by the security tests."""

from __future__ import annotations

import json
from typing import Any

from django_admin_graph.schema import AdminGraph


def assert_closed(graph: AdminGraph) -> None:
    """Every id referenced by an edge or a relation is a node in the graph."""
    ids = {n.id for n in graph.nodes}
    for edge in graph.edges:
        assert edge.source in ids, edge
        assert edge.target in ids, edge
    for model in graph.models:
        for f in model.fields:
            if f.relation is not None and f.relation.target is not None:
                assert f.relation.target in ids, (model.id, f.name)
    for admin in graph.admins:
        assert set(admin.inlines) <= ids


def dumped(graph: AdminGraph | dict[str, Any]) -> str:
    data = graph.to_dict() if isinstance(graph, AdminGraph) else graph
    return json.dumps(data)
