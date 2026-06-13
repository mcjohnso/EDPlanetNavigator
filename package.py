#!/usr/bin/env python3
"""Build a distributable zip of the EDPlanetNavigator EDMC plugin.

Produces ``dist/EDPlanetNavigator-v<version>.zip`` containing the plugin folder
(so it extracts straight into EDMC's ``plugins`` directory). Python caches are
excluded. The version is read from ``EDPlanetNavigator/load.py`` so it stays in
sync with the plugin.

Usage:
    python package.py
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLUGIN_DIR = ROOT / "EDPlanetNavigator"
DIST_DIR = ROOT / "dist"

_EXCLUDE_DIRS = {"__pycache__"}
_EXCLUDE_SUFFIXES = (".pyc", ".pyo")


def read_version() -> str:
    text = (PLUGIN_DIR / "load.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not match:
        sys.exit("Could not find __version__ in EDPlanetNavigator/load.py")
    return match.group(1)


def build() -> Path:
    if not PLUGIN_DIR.is_dir():
        sys.exit(f"Plugin folder not found: {PLUGIN_DIR}")

    version = read_version()
    DIST_DIR.mkdir(exist_ok=True)
    out_path = DIST_DIR / f"EDPlanetNavigator-v{version}.zip"
    if out_path.exists():
        out_path.unlink()

    file_count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PLUGIN_DIR.rglob("*")):
            if any(part in _EXCLUDE_DIRS for part in path.parts):
                continue
            if path.suffix in _EXCLUDE_SUFFIXES:
                continue
            if path.is_file():
                # arcname like "EDPlanetNavigator/load.py"
                zf.write(path, path.relative_to(ROOT).as_posix())
                file_count += 1

    print(f"Built {out_path.relative_to(ROOT)}  ({file_count} files, v{version})")
    return out_path


if __name__ == "__main__":
    build()
