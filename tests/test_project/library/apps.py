from __future__ import annotations

from django.apps import AppConfig


class LibraryConfig(AppConfig):
    name = "tests.test_project.library"
    label = "library"
    verbose_name = "Library"
    default_auto_field = "django.db.models.BigAutoField"
