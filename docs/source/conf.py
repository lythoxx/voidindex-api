"""Sphinx configuration for VoidIndex API documentation."""

from __future__ import annotations

import os
import sys
from datetime import datetime

# Add project root so autodoc can import the package
PROJECT_ROOT = os.path.abspath("../..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

project = "VoidIndex API"
author = "lythox"
copyright = f"{datetime.now().year}, {author}"
release = "1.0.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autodoc_member_order = "bysource"
autodoc_typehints = "description"

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]