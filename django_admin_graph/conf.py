"""Settings accessors for django-admin-graph.

Every consumer-tunable knob is read through this module, never directly
from ``django.conf.settings``:

.. code-block:: python

    DJANGO_ADMIN_GRAPH = {
        "ADMIN_SITE": "django.contrib.admin.site",  # dotted path to an AdminSite
        "EXCLUDE_APPS": [],                          # app labels never graphed
        "EXCLUDE_MODELS": [],                        # "app_label.modelname" never graphed
    }

Exclusions only ever *remove* nodes; nothing here can widen what a user sees.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.admin import AdminSite
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

NAMESPACE = "DJANGO_ADMIN_GRAPH"

DEFAULTS: dict[str, Any] = {
    "ADMIN_SITE": "django.contrib.admin.site",
    "EXCLUDE_APPS": (),
    "EXCLUDE_MODELS": (),
}


def get(key: str) -> Any:
    """Return the configured value for ``key`` (falling back to the default)."""
    if key not in DEFAULTS:
        raise KeyError(f"Unknown {NAMESPACE} setting: {key!r}")
    user = getattr(settings, NAMESPACE, None) or {}
    if not isinstance(user, dict):
        raise ImproperlyConfigured(f"{NAMESPACE} must be a dict, got {type(user).__name__}")
    return user.get(key, DEFAULTS[key])


def get_admin_site() -> AdminSite:
    """Resolve ``ADMIN_SITE`` (a dotted path or an ``AdminSite`` instance)."""
    value = get("ADMIN_SITE")
    site = import_string(value) if isinstance(value, str) else value
    if not isinstance(site, AdminSite):
        raise ImproperlyConfigured(
            f"{NAMESPACE}['ADMIN_SITE'] must point to an AdminSite, got {type(site).__name__}"
        )
    return site


def excluded_apps() -> frozenset[str]:
    return frozenset(str(a) for a in get("EXCLUDE_APPS"))


def excluded_models() -> frozenset[str]:
    return frozenset(str(m).lower() for m in get("EXCLUDE_MODELS"))
