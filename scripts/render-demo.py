#!/usr/bin/env python3
"""Canonical render entrypoint.

Thin wrapper around demo_engine.cli.main() for direct invocation:
    python3 scripts/render-demo.py --theme glitch --preset short
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from demo_engine.cli import main

if __name__ == "__main__":
    main()
