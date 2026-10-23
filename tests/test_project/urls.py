from __future__ import annotations

from django.contrib import admin
from django.urls import include
from django.urls import path

from tests.test_project.library.admin import ops_site

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ops/", ops_site.urls),
    path("admin-graph/", include("django_admin_graph.urls")),
]
