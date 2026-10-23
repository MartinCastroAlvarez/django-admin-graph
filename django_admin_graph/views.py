"""The optional JSON view: ``GET`` the requesting user's admin graph.

Mount it with ``path("admin-graph/", include("django_admin_graph.urls"))``.
It is staff-only (via ``AdminSite.has_permission``), read-only (``GET`` /
``HEAD``), never cached by shared caches, and returns exactly what
:func:`~django_admin_graph.build_graph` returns for ``request`` — nothing
the user could not already see in the admin.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils.cache import patch_cache_control
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_safe

from django_admin_graph import conf
from django_admin_graph.builder import NotAuthenticated
from django_admin_graph.builder import build_graph


def _error(status: int, message: str) -> JsonResponse:
    response = JsonResponse({"error": message}, status=status)
    patch_cache_control(response, private=True, no_store=True)
    return response


@require_safe
def graph_view(request: HttpRequest) -> HttpResponse:
    """Return the admin graph for ``request.user`` as JSON.

    ``?app=<label>`` (repeatable) restricts it to those apps.
    """
    site = conf.get_admin_site()
    apps = request.GET.getlist("app") or None
    try:
        graph = build_graph(site, request, app_labels=apps)
    except NotAuthenticated:
        return _error(401, "Authentication required.")
    except PermissionDenied:
        return _error(403, "Staff access required.")
    response = JsonResponse(graph.to_dict(), json_dumps_params={"ensure_ascii": False})
    # Per-user content: never let a shared cache serve it to someone else.
    patch_cache_control(response, private=True, no_store=True)
    patch_vary_headers(response, ("Cookie",))
    return response
