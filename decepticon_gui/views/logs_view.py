"""Logs page: container output and app activity."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk

from .. import dockerops, ui
from ..i18n import t

SERVICES = ["litellm", "langgraph", "sandbox", "neo4j",
            "postgres", "skillogy", "web", "cli"]


class LogsView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=ui.COLORS["bg"])
        self.app = app
        self.stream = None
        self._queue = queue.Queue()
        self._poll_job = None
        self._build()
        app.add_log_listener(self._append_app)

    def _build(self):
        head = tk.Frame(self, bg=ui.COLORS["bg"])
        head.pack(fill="x", pady=(0, 12))
        box = tk.Frame(head, bg=ui.COLORS["bg"])
        box.pack(side="left")
        ui.label(box, t("logs.title"), size=18, bold=True).pack(anchor="w")
        ui.label(box, t("logs.subtitle"), size=9,
                 fg=ui.COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(head, bg=ui.COLORS["bg"])
        actions.pack(side="right")
        self.service = ttk.Combobox(actions, values=[t("logs.all")] + SERVICES,
                                    state="readonly", width=12, font=ui.font(9))
        self.service.set(t("logs.all"))
        self.service.pack(side="left", padx=(0, 8))
        ui.button(actions, t("common.clear"), self._clear, "ghost").pack(
            side="left", padx=(0, 6))
        ui.button(actions, t("common.stop"), self._stop, "secondary").pack(
            side="left", padx=(0, 6))
        ui.button(actions, t("logs.follow"), self._start, "primary").pack(side="left")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        self.container_log = self._make_log_tab(notebook, t("logs.tab.container"))
        self.app_log = self._make_log_tab(notebook, t("logs.tab.app"))

    def _make_log_tab(self, notebook, title):
        frame = tk.Frame(notebook, bg=ui.COLORS["panel"])
        notebook.add(frame, text=title)
        text = tk.Text(frame, font=ui.font(9, mono=True), bg=ui.COLORS["term_bg"],
                       fg=ui.COLORS["term_fg"], relief="flat", bd=0, wrap="none",
                       padx=10, pady=8, insertbackground=ui.COLORS["term_fg"])
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.configure(state="disabled")
        return text

    # ------------------------------------------------------------------
    def _append(self, widget, line):
        if not widget.winfo_exists():
            return
        widget.configure(state="normal")
        widget.insert("end", line + "\n")
        widget.see("end")
        count = int(widget.index("end-1c").split(".")[0])
        if count > 4000:
            widget.delete("1.0", "600.0")
        widget.configure(state="disabled")

    def _append_app(self, line):
        try:
            self._append(self.app_log, line)
        except (tk.TclError, AttributeError):
            pass

    # ------------------------------------------------------------------
    def _start(self):
        self._stop()
        choice = self.service.get()
        all_label = t("logs.all")
        services = [s for s in SERVICES if s != "cli"] if choice == all_label else [choice]
        self._append(self.container_log,
                     f"$ docker compose logs -f --tail 200 {' '.join(services)}")
        self.stream = dockerops.logs_stream(
            services,
            on_line=self._queue.put,
            on_exit=lambda code: self._queue.put(t("logs.exit", code=code)),
            tail=200)
        self._poll()

    def _poll(self):
        drained = 0
        while drained < 400:
            try:
                line = self._queue.get_nowait()
            except queue.Empty:
                break
            self._append(self.container_log, line)
            drained += 1
        self._poll_job = self.after(120, self._poll)

    def _stop(self):
        if self.stream:
            self.stream.stop()
            self.stream = None
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except tk.TclError:
                pass
            self._poll_job = None

    def _clear(self):
        for widget in (self.container_log, self.app_log):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")

    def on_show(self):
        pass

    def detach(self):
        self._stop()
