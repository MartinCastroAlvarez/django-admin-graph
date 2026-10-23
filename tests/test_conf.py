"""Settings handling."""

from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from django_admin_graph import conf


def test_defaults() -> None:
    assert conf.get_admin_site().name == "admin"
    assert conf.excluded_apps() == frozenset()
    assert conf.excluded_models() == frozenset()


def test_unknown_key() -> None:
    with pytest.raises(KeyError):
        conf.get("NOPE")


@override_settings(DJANGO_ADMIN_GRAPH=["not", "a", "dict"])
def test_namespace_must_be_a_dict() -> None:
    with pytest.raises(ImproperlyConfigured):
        conf.get("ADMIN_SITE")


@override_settings(DJANGO_ADMIN_GRAPH={"ADMIN_SITE": "tests.test_project.library.models.Book"})
def test_admin_site_must_be_an_admin_site() -> None:
    with pytest.raises(ImproperlyConfigured):
        conf.get_admin_site()


def test_admin_site_instance_is_accepted() -> None:
    from tests.test_project.library.admin import ops_site

    with override_settings(DJANGO_ADMIN_GRAPH={"ADMIN_SITE": ops_site}):
        assert conf.get_admin_site() is ops_site


@override_settings(DJANGO_ADMIN_GRAPH={"EXCLUDE_MODELS": ["Library.Book"]})
def test_excluded_models_are_case_insensitive() -> None:
    assert conf.excluded_models() == frozenset({"library.book"})
