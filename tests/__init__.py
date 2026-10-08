"""Test package bootstrap for the src-layout project.

Importing this package (which `python -m unittest discover -s tests` does
before collecting test modules) prepends `src/` to `sys.path`, so the
documented command works on a fresh clone without `pip install -e .` and
without requiring the reader to set PYTHONPATH by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))