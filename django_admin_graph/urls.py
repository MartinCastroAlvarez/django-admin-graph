"""URLconf for the optional JSON view.

.. code-block:: python

    urlpatterns = [
        path("admin/", admin.site.urls),
        path("admin-graph/", include("django_admin_graph.urls")),
    ]
"""

from __future__ import annotations

from django.urls import path

from django_admin_graph.views import graph_view

app_name = "django_admin_graph"

urlpatterns = [
    path("", graph_view, name="graph"),
]
