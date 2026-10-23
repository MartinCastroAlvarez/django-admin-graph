"""GraphViz DOT exporter.

Models become record-shaped nodes clustered by app; relation edges are
solid (FK, O2O) or double-headed (M2M); inline-of edges are dashed, from the
inline's model to the parent model. Render with ``dot -Tsvg graph.dot``.
"""

from __future__ import annotations

from django_admin_graph.schema import AdminGraph

_STYLE = {
    "foreign_key": 'arrowhead="normal"',
    "one_to_one": 'arrowhead="tee"',
    "many_to_many": 'arrowhead="crow", arrowtail="crow", dir="both"',
}


def _q(text: str) -> str:
    """A DOT double-quoted string."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _record(text: str) -> str:
    """Escape text for use inside a ``shape=record`` label."""
    for ch in '\\{}|<>"':
        text = text.replace(ch, "\\" + ch)
    return text.replace("\n", " ")


def to_dot(graph: AdminGraph, *, name: str = "admin") -> str:
    """Render models, relations and inlines as a GraphViz ``digraph``."""
    lines = [
        f"digraph {_q(name)} {{",
        "    rankdir=LR;",
        '    node [shape=record, fontname="Helvetica", fontsize=10];',
        '    edge [fontname="Helvetica", fontsize=9];',
    ]
    model_ids = {m.id for m in graph.models}
    for i, app in enumerate(graph.apps):
        lines.append(f"    subgraph cluster_{i} {{")
        lines.append(f"        label={_q(app.name)};")
        for model in (m for m in graph.models if m.app == app.id):
            rows = "\\l".join(_record(f"{f.name}: {f.field_class or f.type}") for f in model.fields)
            label = "{" + _record(model.label) + ("|" + rows + "\\l" if rows else "") + "}"
            lines.append(f'        {_q(model.id)} [label="{label}"];')
        lines.append("    }")
    for edge in graph.relations():
        style = _STYLE[edge.kind]
        lines.append(
            f"    {_q(edge.source)} -> {_q(edge.target)} [label={_q(edge.field or '')}, {style}];"
        )
    for inline in graph.inlines:
        admin = graph.node(inline.admin)
        parent = getattr(admin, "model", None)
        if inline.model in model_ids and parent in model_ids:
            lines.append(
                f"    {_q(inline.model)} -> {_q(str(parent))} "
                '[style="dashed", label="inline", arrowhead="odiamond"];'
            )
    lines.append("}")
    return "\n".join(lines) + "\n"
