"""JSON exporter — the canonical serialisation of the graph."""

from __future__ import annotations

import json

from django_admin_graph.schema import AdminGraph


def to_json(graph: AdminGraph, *, indent: int | None = 2) -> str:
    """Serialise ``graph`` to the JSON document described in ``docs/schema.md``.

    Output is deterministic (node and edge order come from the builder,
    keys are emitted in schema order), so it diffs cleanly in version control.
    """
    return json.dumps(graph.to_dict(), indent=indent, ensure_ascii=False) + "\n"
