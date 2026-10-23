"""Change form vs add form resolution."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib import admin
from django.http import HttpRequest

from django_admin_graph import build_graph
from tests.test_project.library.models import Tag

pytestmark = pytest.mark.django_db


class NeedsSavedObjectAdmin(admin.ModelAdmin):
    def get_fields(self, request: HttpRequest, obj: Any = None) -> Any:
        if obj is not None and obj.pk is None:
            raise ValueError("this admin only understands saved objects")
        return super().get_fields(request, obj)


class SplitFormsAdmin(admin.ModelAdmin):
    fields = ("name",)

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> Any:
        return ("name",) if obj is not None else ()


def test_user_admin_shows_its_change_form() -> None:
    user = build_graph(app_labels=["auth"]).admin_for("auth.user")
    assert user is not None
    assert {"username", "groups", "is_staff", "user_permissions"} <= set(user.fields)
    assert {"username", "password1", "password2"} <= set(user.add_fields)
    assert [fs.name for fs in user.fieldsets][0] is None
    model = build_graph(app_labels=["auth"]).model("auth.user")
    assert model is not None
    assert model.field("groups") is not None


def test_admin_that_needs_a_saved_object_falls_back_to_add_form() -> None:
    site = admin.AdminSite(name="fussy")
    site.register(Tag, NeedsSavedObjectAdmin)
    tag = build_graph(site).admin_for("library.tag")
    assert tag is not None
    assert tag.fields == ("name",)


def test_add_only_user_sees_the_add_form(request_for: Any, make_user: Any) -> None:
    site = admin.AdminSite(name="split")
    site.register(Tag, SplitFormsAdmin)
    adder = make_user("adder", "library.add_tag", is_staff=True)
    graph = build_graph(site, request_for(adder))
    tag = graph.admin_for("library.tag")
    assert tag is not None
    assert tag.fields == ()
    assert tag.add_fields == ("name",)
    assert tag.readonly_fields == ()
    assert set(tag.url_names) == {"add"}
    model = graph.model("library.tag")
    assert model is not None
    assert model.field("name").readonly is False


def test_viewer_sees_change_form_readonly(request_for: Any, make_user: Any) -> None:
    site = admin.AdminSite(name="split")
    site.register(Tag, SplitFormsAdmin)
    viewer = make_user("tagviewer", "library.view_tag", is_staff=True)
    tag = build_graph(site, request_for(viewer)).admin_for("library.tag")
    assert tag is not None
    assert tag.readonly_fields == ("name",)
    assert tag.add_fields == ()
