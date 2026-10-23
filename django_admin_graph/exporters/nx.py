"""networkx exporter (optional extra: ``pip install "django-admin-graph[networkx]"``)."""

from __future__ import annotations

from typing import Any

from django_admin_graph.schema import AdminGraph


def to_networkx(graph: AdminGraph) -> Any:
    """Return a ``networkx.MultiDiGraph``.

    Every node carries its serialised attributes (``kind``, ``label``, …);
    every edge is keyed by its ``kind`` and carries ``field`` / ``null``.
    """
    try:
        import networkx as nx
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            'to_networkx needs networkx: pip install "django-admin-graph[networkx]"'
        ) from exc
    g = nx.MultiDiGraph(schema_version=graph.schema_version, scope=graph.scope)
    for node in graph.nodes:
        attrs = node.to_dict()
        node_id = attrs.pop("id")
        g.add_node(node_id, **attrs)
    for edge in graph.edges:
        g.add_edge(edge.source, edge.target, key=edge.kind, field=edge.field, null=edge.null)
    return g
