"""GUI preferences, stored outside the Decepticon installation."""

from __future__ import annotations

import json

from . import paths

DEFAULTS = {
    "last_page": "dashboard",
    "terminal_font_size": 11,
    "terminal_shell": "",          # empty = auto (decepticon CLI)
    "language": "auto",            # auto | zh | en
    "theme": "auto",               # auto | light | dark
    "window": "",                  # empty = pick a size that fits the desktop
}


class Settings:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            raw = json.loads(paths.settings_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(raw, dict):
            self._data.update({k: v for k, v in raw.items() if k in DEFAULTS or k.startswith("ui_")})

    def save(self):
        try:
            paths.settings_path().write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def get(self, key, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self._data[key] = value
        self.save()
