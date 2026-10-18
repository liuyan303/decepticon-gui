"""Terminal page."""

from __future__ import annotations

import subprocess
import tkinter as tk

from .. import dockerops, paths, ui
from ..i18n import t
from ..terminal import TerminalFrame


class TerminalView(tk.Frame):
    def __init__(self, parent, app, session=None):
        super().__init__(parent, bg=ui.COLORS["bg"])
        self.app = app
        self._build(session)

    def _build(self, session):
        head = tk.Frame(self, bg=ui.COLORS["bg"])
        head.pack(fill="x", pady=(0, 12))
        box = tk.Frame(head, bg=ui.COLORS["bg"])
        box.pack(side="left")
        ui.label(box, t("term.title"), size=18, bold=True).pack(anchor="w")
        ui.label(box, t("term.subtitle"), size=9,
                 fg=ui.COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(head, bg=ui.COLORS["bg"])
        actions.pack(side="right")
        ui.button(actions, "A-", lambda: self._font(-1), "ghost", width=2).pack(
            side="left", padx=(0, 4))
        ui.button(actions, "A+", lambda: self._font(1), "ghost", width=2).pack(
            side="left", padx=(0, 10))
        ui.button(actions, t("term.clear"), self._clear, "ghost").pack(
            side="left", padx=(0, 6))
        ui.button(actions, t("term.external"), self._open_external, "secondary").pack(
            side="left", padx=(0, 6))
        ui.button(actions, t("common.stop"), self._stop, "secondary").pack(
            side="left", padx=(0, 6))
        ui.button(actions, t("term.start"), self._start, "primary").pack(side="left")

        shell = tk.Frame(self, bg=ui.COLORS["panel"], highlightthickness=1,
                         highlightbackground=ui.COLORS["border"])
        shell.pack(fill="both", expand=True)
        self.term = TerminalFrame(shell, self.app.settings, session=session,
                                  on_status=self._status)
        self.term.pack(fill="both", expand=True)

        bar = tk.Frame(self, bg=ui.COLORS["bg"])
        bar.pack(fill="x", pady=(8, 0))
        self.status = ui.label(bar, t("term.status.idle"), size=9,
                               fg=ui.COLORS["muted"])
        self.status.pack(side="left")
        self.size_label = ui.label(bar, "", size=9, fg=ui.COLORS["muted"])
        self.size_label.pack(side="right")
        self._refresh_labels()

    # ------------------------------------------------------------------
    def _status(self, text, tone="muted"):
        if not self.status.winfo_exists():
            return
        color = {"ok": ui.COLORS["ok"], "warn": ui.COLORS["warn"],
                 "bad": ui.COLORS["bad"]}.get(tone, ui.COLORS["muted"])
        self.status.configure(text=f"● {text}", fg=color)
        self._refresh_labels()

    def _refresh_labels(self):
        term = self.term
        backend = term.backend_name or ("ConPTY" if term.running() else "—")
        self.size_label.configure(
            text=f"{term.screen.cols} × {term.screen.rows}  ·  {backend}")

    def _start(self):
        self.term.start()
        if not self.term.running():
            self._status(t("term.status.idle"), "warn")
        self._refresh_labels()

    def _stop(self):
        self.term.stop()
        self._status(t("term.status.stopped"), "muted")

    def _clear(self):
        self.term.reset_screen()

    def _font(self, delta):
        size = int(self.app.settings.get("terminal_font_size", 11)) + delta
        self.term.set_font_size(size)
        self._refresh_labels()

    def _open_external(self):
        cmd = dockerops.cli_command()
        if not cmd:
            self.app.notify(t("term.need_cli"), "warn")
            return
        line = " ".join(f'"{c}"' if " " in c else c for c in cmd) \
            if isinstance(cmd, list) else cmd
        home = paths.decepticon_home()
        subprocess.Popen(
            ["powershell", "-NoExit", "-Command", line],
            cwd=str(home) if home.is_dir() else None,
            creationflags=0x00000010,  # CREATE_NEW_CONSOLE
        )

    # ------------------------------------------------------------------
    def on_show(self):
        self.term.text.focus_set()

    def run_command(self, command):
        self.term.stop()
        self.term.start(command)
        if not self.term.running():
            self._status(t("term.status.failed"), "bad")
        self._refresh_labels()
