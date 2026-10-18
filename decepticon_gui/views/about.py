"""About page: attribution, license, disclaimer."""

from __future__ import annotations

import tkinter as tk
import webbrowser

from .. import __version__, ui
from ..i18n import t


class AboutView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=ui.COLORS["bg"])
        self.app = app
        self._build()

    def _build(self):
        head = tk.Frame(self, bg=ui.COLORS["bg"])
        head.pack(fill="x", pady=(0, 14))
        ui.label(head, t("about.title"), size=18, bold=True).pack(anchor="w")
        ui.label(head, t("about.subtitle"), size=9,
                 fg=ui.COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        card = ui.Card(self, t("about.license"))
        card.pack(fill="both", expand=True, pady=(12, 0))
        text = tk.Text(card.body, font=ui.font(9, mono=True), bg=ui.COLORS["panel_alt"],
                       fg=ui.COLORS["text"], relief="flat", bd=0, wrap="word",
                       padx=12, pady=10)
        text.pack(fill="both", expand=True)
        text.insert("1.0", t("about.notice", version=__version__))
        text.configure(state="disabled")

        links = tk.Frame(card.body, bg=ui.COLORS["panel"])
        links.pack(fill="x", pady=(10, 0))
        ui.button(links, t("about.upstream"), lambda: webbrowser.open(
            "https://github.com/PurpleAILAB/Decepticon"), "secondary").pack(side="left")
        ui.button(links, t("about.docs"), lambda: webbrowser.open(
            "https://docs.decepticon.red"), "secondary").pack(side="left", padx=8)
        ui.button(links, t("about.apache"), lambda: webbrowser.open(
            "https://www.apache.org/licenses/LICENSE-2.0"), "ghost").pack(side="left")

        warn = ui.Card(self, t("about.disclaimer"))
        warn.pack(fill="x", pady=(12, 0))
        ui.label(warn.body, t("about.disclaimer.body"), size=9,
                 fg=ui.COLORS["muted"], justify="left",
                 wraplength=900).pack(anchor="w")

    def on_show(self):
        pass
