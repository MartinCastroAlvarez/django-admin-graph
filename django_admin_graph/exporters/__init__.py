"""Exporters: turn an :class:`~django_admin_graph.schema.AdminGraph` into text.

* :func:`to_json` — the canonical, versioned document (``docs/schema.md``).
* :func:`to_mermaid` — a Mermaid ``erDiagram`` of models and relations.
* :func:`to_dot` — a GraphViz ``digraph`` (models clustered by app).
* :func:`to_networkx` — a ``networkx.MultiDiGraph`` (optional extra).
"""

from __future__ import annotations

from django_admin_graph.exporters.dot import to_dot
from django_admin_graph.exporters.json import to_json
from django_admin_graph.exporters.mermaid import to_mermaid
from django_admin_graph.exporters.nx import to_networkx

FORMATS = ("json", "mermaid", "dot")

__all__ = ["FORMATS", "to_dot", "to_json", "to_mermaid", "to_networkx"]
