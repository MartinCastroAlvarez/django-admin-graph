#!/usr/bin/env python
"""Read a saved graph without Django and print an agent-facing summary.

This is the shape of what ``django-admin-skills`` does: it never imports the
project, it only reads the versioned JSON document.

    python examples/quickstart/manage.py admin_graph -o graph.json
    python examples/consume_graph.py graph.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from django_admin_graph.schema import AdminGraph  # noqa: E402 — after sys.path


def summarise(graph: AdminGraph) -> str:
    lines = [f"# {graph.site.site_header} (schema {graph.schema_version}, {graph.scope})"]
    for model in graph.models:
        admin = graph.admin_for(model.label)
        lines.append(f"\n## {model.label} — {model.verbose_name_plural}")
        lines.append("fields: " + ", ".join(f"{f.name}:{f.field_class}" for f in model.fields))
        for edge in graph.edges_from(model.id):
            if edge.kind in ("foreign_key", "one_to_one", "many_to_many"):
                lines.append(f"{edge.field} -> {edge.target} ({edge.kind})")
        if admin is not None:
            granted = [k for k, v in admin.permissions.to_dict().items() if v]
            lines.append("can: " + ", ".join(granted))
            if admin.search_fields:
                lines.append("search: " + ", ".join(admin.search_fields))
            for action in admin.actions:
                lines.append(f"action {action.name}: {action.description}")
    return "\n".join(lines)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("graph.json")
    print(summarise(AdminGraph.from_dict(json.loads(path.read_text()))))
