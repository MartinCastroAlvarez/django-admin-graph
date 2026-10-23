"""Mermaid ``erDiagram`` exporter.

Entities are models (``APP_MODEL``), attributes are the fields the admin
exposes, and relationships are the FK / O2O / M2M edges in the graph.
"""

from __future__ import annotations

import re

from django_admin_graph.schema import AdminGraph
from django_admin_graph.schema import ModelNode

_UNSAFE = re.compile(r"[^A-Za-z0-9_]")

# (source cardinality, target cardinality) in Mermaid crow's-foot notation,
# read "source <left>--<right> target".
_CARDINALITY = {
    ("foreign_key", False): "}o--||",
    ("foreign_key", True): "}o--o|",
    ("one_to_one", False): "|o--||",
    ("one_to_one", True): "|o--o|",
    ("many_to_many", False): "}o--o{",
    ("many_to_many", True): "}o--o{",
}


def _entity(model: ModelNode) -> str:
    return _UNSAFE.sub("_", model.label.replace(".", "_")).upper()


def _word(text: str) -> str:
    return _UNSAFE.sub("_", text) or "_"


def _quote(text: str) -> str:
    return '"' + text.replace('"', "'").replace("\n", " ") + '"'


def to_mermaid(graph: AdminGraph) -> str:
    """Render the models and their relations as a Mermaid ``erDiagram``."""
    lines = ["erDiagram"]
    entities: dict[str, str] = {}
    for model in graph.models:
        entities[model.id] = _entity(model)
        lines.append(f"    {entities[model.id]} {{")
        for f in model.fields:
            keys = []
            if f.primary_key:
                keys.append("PK")
            if f.relation is not None and f.relation.kind != "many_to_many":
                keys.append("FK")
            if f.unique and not f.primary_key:
                keys.append("UK")
            key = f" {','.join(keys)}" if keys else ""
            comment = f" {_quote(f.verbose_name)}" if f.verbose_name else ""
            lines.append(f"        {_word(f.field_class or f.type)} {_word(f.name)}{key}{comment}")
        lines.append("    }")
    for edge in graph.relations():
        if edge.source not in entities or edge.target not in entities:
            continue
        arrow = _CARDINALITY[(edge.kind, bool(edge.null))]
        label = _quote(edge.field or edge.kind)
        lines.append(f"    {entities[edge.source]} {arrow} {entities[edge.target]} : {label}")
    return "\n".join(lines) + "\n"
