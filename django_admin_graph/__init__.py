"""django-admin-graph — the Django admin site as a typed graph.

>>> from django_admin_graph import build_graph, to_json
>>> graph = build_graph()                  # offline: the whole site
>>> graph = build_graph(request=request)   # what this user can see
>>> to_json(graph)

See ``docs/schema.md`` for the JSON contract.
"""

from __future__ import annotations

__version__ = "0.1.0"

from django_admin_graph.builder import NotAuthenticated
from django_admin_graph.builder import build_graph
from django_admin_graph.exporters import to_dot
from django_admin_graph.exporters import to_json
from django_admin_graph.exporters import to_mermaid
from django_admin_graph.exporters import to_networkx
from django_admin_graph.schema import SCHEMA_VERSION
from django_admin_graph.schema import ActionInfo
from django_admin_graph.schema import AdminGraph
from django_admin_graph.schema import AdminNode
from django_admin_graph.schema import AppNode
from django_admin_graph.schema import Edge
from django_admin_graph.schema import FieldInfo
from django_admin_graph.schema import InlineNode
from django_admin_graph.schema import ModelNode
from django_admin_graph.schema import PermissionNode
from django_admin_graph.schema import Permissions
from django_admin_graph.schema import Relation
from django_admin_graph.schema import SchemaVersionError

__all__ = [
    "SCHEMA_VERSION",
    "ActionInfo",
    "AdminGraph",
    "AdminNode",
    "AppNode",
    "Edge",
    "FieldInfo",
    "InlineNode",
    "ModelNode",
    "NotAuthenticated",
    "PermissionNode",
    "Permissions",
    "Relation",
    "SchemaVersionError",
    "__version__",
    "build_graph",
    "to_dot",
    "to_json",
    "to_mermaid",
    "to_networkx",
]
