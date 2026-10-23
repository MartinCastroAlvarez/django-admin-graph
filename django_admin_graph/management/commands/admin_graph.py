"""``manage.py admin_graph`` — print or save the admin graph.

Runs offline as the unrestricted system user (see ``builder.py``): it shows
the whole site, so treat its output like your code, not like public docs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from django.contrib.admin import AdminSite
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils.module_loading import import_string

from django_admin_graph import conf
from django_admin_graph.builder import build_graph
from django_admin_graph.exporters import FORMATS
from django_admin_graph.exporters import to_dot
from django_admin_graph.exporters import to_json
from django_admin_graph.exporters import to_mermaid


class Command(BaseCommand):
    help = "Export the Django admin site as a graph (JSON, Mermaid erDiagram or GraphViz DOT)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--format", choices=FORMATS, default="json", help="Output format.")
        parser.add_argument(
            "--output", "-o", default=None, help="Write to this file instead of stdout."
        )
        parser.add_argument(
            "--app",
            action="append",
            dest="apps",
            default=None,
            help="Only include this app label (repeatable).",
        )
        parser.add_argument(
            "--site",
            default=None,
            help="Dotted path to an AdminSite (default: the ADMIN_SITE setting).",
        )
        parser.add_argument("--indent", type=int, default=2, help="JSON indent (0 for compact).")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            site = import_string(options["site"]) if options["site"] else conf.get_admin_site()
        except ImportError as exc:
            raise CommandError(f"Cannot import admin site {options['site']!r}: {exc}") from exc
        if not isinstance(site, AdminSite):
            raise CommandError(f"{options['site']!r} is not an AdminSite")
        graph = build_graph(site, app_labels=options["apps"])
        fmt = options["format"]
        if fmt == "mermaid":
            text = to_mermaid(graph)
        elif fmt == "dot":
            text = to_dot(graph, name=site.name)
        else:
            text = to_json(graph, indent=options["indent"] or None)
        if options["output"]:
            Path(options["output"]).write_text(text, encoding="utf-8")
            self.stderr.write(f"Wrote {fmt} graph to {options['output']}")
        else:
            self.stdout.write(text, ending="")
