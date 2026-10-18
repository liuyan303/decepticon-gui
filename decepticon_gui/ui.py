"""Theme palettes and small widget helpers.

Two palettes are defined with the same keys. ``set_theme`` swaps the
contents of COLORS in place, so every widget built afterwards picks up
the new colours; the app rebuilds its views on a theme change.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

LIGHT = {
    "bg": "#f5f6f8",
    "panel": "#ffffff",
    "panel_alt": "#fbfbfc",
    "input_bg": "#ffffff",
    "input_border": "#d8dce3",
    "border": "#e3e6eb",
    "text": "#1c2024",
    "muted": "#6b7280",
    "accent": "#6d4aff",
    "accent_dark": "#5636e0",
    "accent_soft": "#efeaff",
    "on_accent": "#ffffff",
    "ok": "#0f9d58",
    "warn": "#c77700",
    "bad": "#d13438",
    "sidebar": "#ffffff",
    "hover": "#f2f3f7",
    "secondary": "#eceef2",
    "secondary_active": "#e0e3e9",
    "ghost_hover": "#e9ebef",
    "danger_bg": "#fdecec",
    "danger_active": "#f8dada",
    "chip_muted_bg": "#eceef2",
    "chip_ok_bg": "#e7f6ee",
    "chip_warn_bg": "#fdf3e2",
    "chip_bad_bg": "#fdeaea",
    "chip_accent_bg": "#efeaff",
    "term_bg": "#fbfbfc",
    "term_fg": "#24292f",
    "term_sel": "#d8defc",
    "term_cursor_fg": "#ffffff",
}

DARK = {
    "bg": "#101216",
    "panel": "#181b21",
    "panel_alt": "#1f232b",
    "input_bg": "#232830",
    "input_border": "#3a424d",
    "border": "#2a2f38",
    "text": "#e6e8ec",
    "muted": "#98a1ad",
    "accent": "#8b6bff",
    "accent_dark": "#b9a5ff",
    "accent_soft": "#2a2340",
    "on_accent": "#ffffff",
    "ok": "#3fb950",
    "warn": "#d29922",
    "bad": "#f85149",
    "sidebar": "#14171c",
    "hover": "#21262e",
    "secondary": "#232830",
    "secondary_active": "#2d333d",
    "ghost_hover": "#1f242b",
    "danger_bg": "#3a1b1d",
    "danger_active": "#4a2225",
    "chip_muted_bg": "#232830",
    "chip_ok_bg": "#16301f",
    "chip_warn_bg": "#33260f",
    "chip_bad_bg": "#3a1b1d",
    "chip_accent_bg": "#2a2340",
    "term_bg": "#0c0e12",
    "term_fg": "#d7dae0",
    "term_sel": "#2d3340",
    "term_cursor_fg": "#0c0e12",
}

PALETTES = {"light": LIGHT, "dark": DARK}
COLORS = dict(LIGHT)
_current = "light"

UI_FONT = "Segoe UI"
MONO_FONT = "Consolas"

ANSI_DARK_FIRST16 = [
    "#1c1c1c", "#cd3131", "#0dbc79", "#e5e510", "#2472c8", "#bc3fbc",
    "#11a8cd", "#e5e5e5", "#666666", "#f14c4c", "#23d18b", "#f5f543",
    "#3b8eea", "#d670d6", "#29b8db", "#ffffff",
]
ANSI_LIGHT_FIRST16 = [
    "#1c1c1c", "#b91c1c", "#0a7d4f", "#8a6d00", "#1d4ed8", "#8b2f8b",
    "#0e7490", "#4b5563", "#6b7280", "#dc2626", "#047857", "#a16207",
    "#2563eb", "#7e22ce", "#0e7490", "#111827",
]


def _build_palette_256(first16):
    palette = list(first16)
    levels = [0, 95, 135, 175, 215, 255]
    for r in levels:
        for g in levels:
            for b in levels:
                palette.append(f"#{r:02x}{g:02x}{b:02x}")
    for i in range(24):
        v = 8 + i * 10
        palette.append(f"#{v:02x}{v:02x}{v:02x}")
    return palette


ANSI_DARK = _build_palette_256(ANSI_DARK_FIRST16)
ANSI_LIGHT = _build_palette_256(ANSI_LIGHT_FIRST16)


def ansi_palette():
    return ANSI_LIGHT if _current == "light" else ANSI_DARK


def set_theme(name):
    global _current
    _current = name if name in PALETTES else "light"
    COLORS.clear()
    COLORS.update(PALETTES[_current])


def current_theme():
    return _current


def preferred_theme() -> str:
    """Follow the Windows app theme on first run."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value else "dark"
    except Exception:  # noqa: BLE001 - non-Windows or locked down
        return "light"


def font(size=10, bold=False, mono=False, italic=False):
    family = MONO_FONT if mono else UI_FONT
    return (family, size, ("bold" if bold else "") + ("italic" if italic else ""))


def label(parent, text, size=10, bold=False, fg=None, bg=None, mono=False, **kw):
    options = {"anchor": "w", "justify": "left"}
    options.update(kw)
    return tk.Label(
        parent, text=text, font=font(size, bold, mono),
        fg=fg or COLORS["text"], bg=bg or parent.cget("bg"), **options,
    )


def button(parent, text, command, kind="secondary", width=None):
    palette = {
        "primary": (COLORS["accent"], COLORS["on_accent"], COLORS["accent_dark"]),
        "secondary": (COLORS["secondary"], COLORS["text"], COLORS["secondary_active"]),
        "ghost": (parent.cget("bg"), COLORS["muted"], COLORS["ghost_hover"]),
        "danger": (COLORS["danger_bg"], COLORS["bad"], COLORS["danger_active"]),
    }[kind]
    return tk.Button(
        parent, text=text, command=command, font=font(9, bold=(kind == "primary")),
        bg=palette[0], fg=palette[1], activebackground=palette[2],
        activeforeground=palette[1], relief="flat", bd=0, padx=14, pady=6,
        cursor="hand2", highlightthickness=0, width=width,
    )


class Card(tk.Frame):
    """Panel with an optional title row and a body frame."""

    def __init__(self, parent, title=None, subtitle=None, padding=16):
        super().__init__(parent, bg=COLORS["panel"], highlightthickness=1,
                         highlightbackground=COLORS["border"])
        self.body = tk.Frame(self, bg=COLORS["panel"])
        if title:
            head = tk.Frame(self, bg=COLORS["panel"])
            head.pack(fill="x", padx=padding, pady=(padding, 0))
            tk.Label(head, text=title, font=font(10, True), fg=COLORS["text"],
                     bg=COLORS["panel"], anchor="w").pack(side="left")
            self.head = head
            if subtitle:
                tk.Label(head, text=subtitle, font=font(9), fg=COLORS["muted"],
                         bg=COLORS["panel"], anchor="w").pack(side="left", padx=(8, 0))
        self.body.pack(fill="both", expand=True, padx=padding,
                       pady=(10 if title else padding, padding))


class Pill(tk.Label):
    def __init__(self, parent, text="", tone="muted"):
        self._tones = {
            "muted": (COLORS["chip_muted_bg"], COLORS["muted"]),
            "ok": (COLORS["chip_ok_bg"], COLORS["ok"]),
            "warn": (COLORS["chip_warn_bg"], COLORS["warn"]),
            "bad": (COLORS["chip_bad_bg"], COLORS["bad"]),
            "accent": (COLORS["chip_accent_bg"], COLORS["accent_dark"]),
        }
        bg, fg = self._tones.get(tone, self._tones["muted"])
        super().__init__(parent, text=text, font=font(8, True), bg=bg, fg=fg,
                         padx=8, pady=2)

    def set(self, text, tone="muted"):
        bg, fg = self._tones.get(tone, self._tones["muted"])
        self.configure(text=text, bg=bg, fg=fg)


def separator(parent, pady=8):
    line = tk.Frame(parent, bg=COLORS["border"], height=1)
    line.pack(fill="x", pady=pady)
    return line


def entry(parent, width=None, show=None, justify="left", font_size=9, pad_y=5):
    """Bordered single-line input. Returns (container, tk.Entry)."""
    box = tk.Frame(parent, bg=COLORS["input_border"], padx=1, pady=1)
    widget = tk.Entry(
        box, relief="flat", bd=0, bg=COLORS["input_bg"], fg=COLORS["text"],
        insertbackground=COLORS["text"], font=font(font_size, mono=True),
        show=show or "", justify=justify, width=width or 0,
        highlightthickness=0,
    )
    widget.pack(fill="both", expand=True, ipady=pad_y, ipadx=4)
    return box, widget


def init_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TCombobox", fieldbackground=COLORS["input_bg"],
                    background=COLORS["input_bg"], foreground=COLORS["text"],
                    arrowcolor=COLORS["muted"], bordercolor=COLORS["border"],
                    lightcolor=COLORS["border"], darkcolor=COLORS["border"],
                    padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", COLORS["input_bg"])],
              foreground=[("readonly", COLORS["text"])],
              bordercolor=[("focus", COLORS["accent"])])
    root.option_add("*TCombobox*Listbox.background", COLORS["panel"])
    root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["accent_soft"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["text"])

    style.configure("Treeview", background=COLORS["panel"],
                    fieldbackground=COLORS["panel"], foreground=COLORS["text"],
                    rowheight=26, borderwidth=0, font=font(9),
                    bordercolor=COLORS["border"], lightcolor=COLORS["panel"],
                    darkcolor=COLORS["panel"], relief="flat")
    style.configure("Treeview.Heading", background=COLORS["panel"],
                    foreground=COLORS["muted"], font=font(9, True),
                    borderwidth=0, relief="flat")
    style.map("Treeview.Heading", background=[("active", COLORS["panel"])])
    style.map("Treeview", background=[("selected", COLORS["accent_soft"])],
              foreground=[("selected", COLORS["text"])])

    style.configure("TScrollbar", background=COLORS["border"],
                    troughcolor=COLORS["panel"], borderwidth=0,
                    arrowcolor=COLORS["muted"])
    style.configure("TNotebook", background=COLORS["bg"], borderwidth=0,
                    tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", font=font(9), padding=(14, 5),
                    background=COLORS["secondary"], foreground=COLORS["muted"],
                    borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", COLORS["panel"])],
              foreground=[("selected", COLORS["text"])])
    return style
