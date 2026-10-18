"""Filesystem locations used by the GUI.

Decepticon itself always lives under DECEPTICON_HOME (default
``%USERPROFILE%\\.decepticon``); this app keeps its own preferences in
``%APPDATA%\\DecepticonGUI`` and never writes into the Decepticon tree
except when the user saves the .env form.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

APP_NAME = "DecepticonGUI"


def decepticon_home() -> Path:
    raw = os.environ.get("DECEPTICON_HOME")
    if raw:
        raw = os.path.expandvars(raw).strip().strip('"')
        if raw and "~" not in raw:
            return Path(raw).expanduser().absolute()
    return Path.home() / ".decepticon"


def launcher_path() -> Path | None:
    candidates = [
        decepticon_home() / "bin" / "decepticon.exe",
        decepticon_home() / "bin" / "decepticon",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    found = shutil.which("decepticon")
    return Path(found) if found else None


def appdata_dir() -> Path:
    base = os.environ.get("APPDATA")
    path = Path(base) / APP_NAME if base else Path.home() / ".decepticon-gui"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return appdata_dir() / "settings.json"


def env_path() -> Path:
    return decepticon_home() / ".env"


def env_example_path() -> Path:
    return decepticon_home() / ".env.example"


def compose_path() -> Path:
    return decepticon_home() / "docker-compose.yml"


def workspace_dir() -> Path:
    return decepticon_home() / "workspace"


def version_file() -> Path:
    return decepticon_home() / ".version"


def installed_version() -> str:
    """Version recorded by the installer, or "" when the file is missing."""
    try:
        return version_file().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def is_installed() -> bool:
    return compose_path().is_file() and launcher_path() is not None
