"""Mermaid, DOT, JSON and networkx exporters."""

from __future__ import annotations

import json

import networkx as nx
import pytest

from django_admin_graph import build_graph
from django_admin_graph import to_dot
from django_admin_graph import to_json
from django_admin_graph import to_mermaid
from django_admin_graph import to_networkx
from django_admin_graph.schema import AdminGraph
from django_admin_graph.schema import AppNode
from django_admin_graph.schema import Edge
from django_admin_graph.schema import FieldInfo
from django_admin_graph.schema import ModelNode
from django_admin_graph.schema import Relation
from django_admin_graph.schema import SiteInfo

pytestmark = pytest.mark.django_db


@pytest.fixture
def library() -> AdminGraph:
    return build_graph(app_labels=["library"])


def test_json_is_indented_and_compactable(library: AdminGraph) -> None:
    pretty = to_json(library)
    compact = to_json(library, indent=None)
    assert pretty.startswith('{\n  "schema_version"')
    assert "\n" not in compact.rstrip("\n")
    assert json.loads(pretty) == json.loads(compact)


def test_mermaid_er_diagram(library: AdminGraph) -> None:
    text = to_mermaid(library)
    assert text.startswith("erDiagram\n")
    assert "    LIBRARY_BOOK {" in text
    assert '        BigAutoField id PK "ID"' in text
    assert '        EmailField email UK "email"' in text
    assert '        ForeignKey author FK "author"' in text
    assert 'LIBRARY_BOOK }o--|| LIBRARY_AUTHOR : "author"' in text
    assert 'LIBRARY_BOOK }o--o| LIBRARY_PUBLISHER : "publisher"' in text
    assert 'LIBRARY_BOOK }o--o{ LIBRARY_TAG : "tags"' in text
    assert 'LIBRARY_AUTHORPROFILE |o--|| LIBRARY_AUTHOR : "author"' in text
    assert "internal_notes" not in text


def test_dot_digraph(library: AdminGraph) -> None:
    text = to_dot(library, name="my site")
    assert text.startswith('digraph "my site" {')
    assert "subgraph cluster_0" in text
    assert 'label="Library";' in text
    assert '"model:library.book" -> "model:library.author" [label="author"' in text
    assert 'dir="both"' in text  # the M2M edge
    assert '"model:library.review" -> "model:library.book" [style="dashed"' in text
    assert text.rstrip().endswith("}")


def _tricky_graph() -> AdminGraph:
    model = ModelNode(
        id="model:x.weird",
        app="app:x",
        label="x.Weird",
        object_name="Weird",
        verbose_name='we"ird',
        verbose_name_plural="weirds",
        pk="id",
        fields=(
            FieldInfo(name="id", type="AutoField", verbose_name='say "hi"', primary_key=True),
            FieldInfo(
                name="parent",
                type="ForeignKey",
                verbose_name="a|b{c}",
                null=True,
                relation=Relation(kind="one_to_one", target="model:x.weird"),
            ),
        ),
    )
    return AdminGraph(
        site=SiteInfo(name="s", site_header="", site_title=""),
        scope="system",
        nodes=(AppNode(id="app:x", label="x", name='X "app"'), model),
        edges=(
            Edge(
                source="model:x.weird",
                target="model:x.weird",
                kind="one_to_one",
                field="parent",
                null=True,
            ),
            Edge(source="model:x.weird", target="model:x.gone", kind="foreign_key", field="g"),
        ),
    )


def test_exporters_escape_hostile_names() -> None:
    graph = _tricky_graph()
    mermaid = to_mermaid(graph)
    assert "\"say 'hi'\"" in mermaid
    assert "X_WEIRD |o--o| X_WEIRD" in mermaid
    assert "x.gone" not in mermaid  # edges to unknown entities are skipped
    dot = to_dot(graph)
    assert 'label="X \\"app\\"";' in dot
    assert "parent: ForeignKey" in dot


def test_networkx(library: AdminGraph) -> None:
    g = to_networkx(library)
    assert isinstance(g, nx.MultiDiGraph)
    assert g.graph["schema_version"] == "1.0"
    assert g.nodes["model:library.book"]["kind"] == "model"
    assert g.has_edge("model:library.book", "model:library.author", key="foreign_key")
    assert g.number_of_nodes() == len(library.nodes)
    assert g.number_of_edges() == len(library.edges)
