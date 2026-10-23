"""manage.py admin_graph."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def run(*args: str) -> str:
    out = StringIO()
    call_command("admin_graph", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def test_default_is_json() -> None:
    data = json.loads(run())
    assert data["scope"] == {"mode": "system"}
    assert any(n["id"] == "model:library.book" for n in data["nodes"])


def test_compact_json() -> None:
    assert "\n" not in run("--indent", "0").rstrip("\n")


def test_mermaid_and_dot() -> None:
    assert run("--format", "mermaid", "--app", "library").startswith("erDiagram")
    assert run("--format", "dot", "--app", "library").startswith('digraph "admin"')


def test_app_filter_is_repeatable() -> None:
    data = json.loads(run("--app", "library", "--app", "auth"))
    assert {n["label"] for n in data["nodes"] if n["kind"] == "app"} == {"library", "auth"}


def test_output_file(tmp_path: Path) -> None:
    target = tmp_path / "graph.mmd"
    assert run("--format", "mermaid", "-o", str(target)) == ""
    assert target.read_text().startswith("erDiagram")


def test_custom_site() -> None:
    data = json.loads(run("--site", "tests.test_project.library.admin.ops_site"))
    assert data["site"]["name"] == "ops"


@pytest.mark.parametrize(
    "site", ["tests.test_project.library.admin.nope", "tests.test_project.library.admin.Tag"]
)
def test_bad_site(site: str) -> None:
    with pytest.raises(CommandError):
        run("--site", site)


def test_bad_format() -> None:
    with pytest.raises(CommandError):
        run("--format", "yaml")
