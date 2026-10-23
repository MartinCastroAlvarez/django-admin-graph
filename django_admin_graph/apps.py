"""Django app configuration."""

from __future__ import annotations

from django.apps import AppConfig


class DjangoAdminGraphConfig(AppConfig):
    name = "django_admin_graph"
    verbose_name = "Django admin graph"
    default_auto_field = "django.db.models.BigAutoField"
