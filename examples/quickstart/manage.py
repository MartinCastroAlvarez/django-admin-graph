#!/usr/bin/env python
"""Run the bundled test project's manage.py from a source checkout.

python examples/quickstart/manage.py admin_graph --format mermaid --app library
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.test_project.settings")

if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
