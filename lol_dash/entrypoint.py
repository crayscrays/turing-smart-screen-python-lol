"""
PyInstaller-friendly entrypoint.

PyInstaller can't run packages with `python -m`, so this thin wrapper just
calls into our real main(). Importable from the project root.

Run from repo root in dev:
    python lol_dash/entrypoint.py
"""

from __future__ import annotations

import os
import sys


def _ensure_repo_root_on_path() -> None:
    """
    When running as a PyInstaller-frozen binary, `sys._MEIPASS` is the bundle
    root. When running from source, it's the repo root. Either way, make sure
    both the repo root and lol_dash/ are importable.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if base not in sys.path:
        sys.path.insert(0, base)


def _chdir_to_runtime_root() -> None:
    """
    When frozen, change the working directory to the directory containing the
    executable so relative paths in config.yaml (lol_dash/videos, etc.) keep
    working when users double-click the binary from anywhere.
    """
    if getattr(sys, "frozen", False):
        # The user-facing 'project root' next to the exe — that's where they
        # put their videos folder, config overrides, etc.
        exe_dir = os.path.dirname(sys.executable)
        os.chdir(exe_dir)


if __name__ == "__main__":
    _ensure_repo_root_on_path()
    _chdir_to_runtime_root()
    from lol_dash.src.main import main
    sys.exit(main())
