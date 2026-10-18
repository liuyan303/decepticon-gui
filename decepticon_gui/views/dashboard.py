"""Overview: environment checks, container table, quick actions."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk

from .. import dockerops, doctor, paths, ui
from ..i18n import t


class DashboardView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=ui.COLORS["bg"])
        self.app = app
        self._busy = False
        self._tasks = queue.Queue()
        self._pump_job = None
        self._build()
        self._pump()

    # ------------------------------------------------------------------
    def _build(self):
        head = tk.Frame(self, bg=ui.COLORS["bg"])
        head.pack(fill="x", pady=(0, 14))
        box = tk.Frame(head, bg=ui.COLORS["bg"])
        box.pack(side="left")
        ui.label(box, t("dash.title"), size=18, bold=True).pack(anchor="w")
        ui.label(box, t("dash.subtitle"), size=9,
                 fg=ui.COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(head, bg=ui.COLORS["bg"])
        actions.pack(side="right")
        self.btn_refresh = ui.button(actions, t("dash.recheck"), self.refresh, "ghost")
        self.btn_refresh.pack(side="left", padx=(0, 6))
        self.btn_start = ui.button(actions, t("common.start"), self.start_stack, "primary")
        self.btn_start.pack(side="left", padx=(0, 6))
        self.btn_stop = ui.button(actions, t("common.stop"), self.stop_stack, "secondary")
        self.btn_stop.pack(side="left")

        # stat row -----------------------------------------------------
        stats = tk.Frame(self, bg=ui.COLORS["bg"])
        stats.pack(fill="x", pady=(0, 14))
        for i in range(3):
            stats.columnconfigure(i, weight=1)
        self.stat_docker = self._stat_card(stats, 0, t("dash.stat.docker"))
        self.stat_stack = self._stat_card(stats, 1, t("dash.stat.stack"))
        self.stat_version = self._stat_card(stats, 2, t("dash.stat.version"))

        body = tk.Frame(self, bg=ui.COLORS["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, uniform="b")
        body.columnconfigure(1, weight=2, uniform="b")
        body.rowconfigure(1, weight=1)

        checks = ui.Card(body, t("dash.checks"), t("dash.checks.hint"))
        checks.grid(row=0, column=0, sticky="new", padx=(0, 12))
        self.check_rows = {}
        for key, title_key, _fn, _hint in doctor.CHECKS:
            row = tk.Frame(checks.body, bg=ui.COLORS["panel"])
            row.pack(fill="x", pady=3)
            dot = tk.Label(row, text="●", font=ui.font(9), bg=ui.COLORS["panel"],
                           fg=ui.COLORS["muted"])
            dot.pack(side="left")
            ui.label(row, t(title_key), size=9).pack(side="left", padx=(8, 0))
            detail = ui.label(row, "…", size=9, fg=ui.COLORS["muted"])
            detail.pack(side="right")
            self.check_rows[key] = (dot, detail)

        side = tk.Frame(body, bg=ui.COLORS["bg"])
        side.grid(row=0, column=1, sticky="new")
        quick = ui.Card(side, t("dash.quick"))
        quick.pack(fill="x")
        for text, cmd in (
            (t("dash.quick.web"), self.open_web),
            (t("dash.quick.neo4j"), lambda: webbrowser.open(dockerops.neo4j_url())),
            (t("dash.quick.workspace"), self.open_workspace),
            (t("dash.quick.terminal"), lambda: self.app.goto("terminal")),
        ):
            btn = ui.button(quick.body, text, cmd, "secondary")
            btn.pack(fill="x", pady=3)

        help_card = ui.Card(side, t("dash.next"))
        help_card.pack(fill="x", pady=(12, 0))
        self.hint = ui.label(
            help_card.body, t("dash.next.body"),
            size=9, fg=ui.COLORS["muted"], justify="left")
        self.hint.pack(anchor="w")

        # containers ---------------------------------------------------
        table = ui.Card(self, t("dash.containers"), t("dash.containers.hint"))
        table.pack(fill="both", expand=True, pady=(12, 0))
        columns = ("service", "state", "health", "ports", "name")
        self.tree = ttk.Treeview(table.body, columns=columns, show="headings",
                                 height=6)
        widths = {"service": 140, "state": 100, "health": 100, "ports": 180, "name": 260}
        titles = {"service": t("dash.col.service"), "state": t("dash.col.state"),
                  "health": t("dash.col.health"), "ports": t("dash.col.ports"),
                  "name": t("dash.col.name")}
        for col in columns:
            self.tree.heading(col, text=titles[col])
            self.tree.column(col, width=widths[col], minwidth=80, anchor="w",
                             stretch=col == "name")
        self.tree.pack(fill="both", expand=True)

    def _stat_card(self, parent, col, title):
        card = ui.Card(parent, padding=14)
        card.grid(row=0, column=col, sticky="ew",
                  padx=(0 if col == 0 else 6, 0 if col == 2 else 6))
        inner = card.body
        ui.label(inner, title, size=9, fg=ui.COLORS["muted"]).pack(anchor="w")
        value = ui.label(inner, "—", size=14, bold=True)
        value.pack(anchor="w", pady=(4, 0))
        card.value = value
        return card

    # ------------------------------------------------------------------
    def _post(self, fn):
        """Hand work to the UI thread from a worker."""
        self._tasks.put(fn)

    def _pump(self):
        self._pump_job = None
        try:
            while True:
                self._tasks.get_nowait()()
        except queue.Empty:
            pass
        if self.winfo_exists():
            self._pump_job = self.after(80, self._pump)

    def on_show(self):
        self.refresh()

    def _alive(self):
        return bool(self.winfo_exists())

    def destroy(self):
        if self._pump_job:
            try:
                self.after_cancel(self._pump_job)
            except tk.TclError:
                pass
            self._pump_job = None
        super().destroy()

    def refresh(self):
        if self._busy:
            return
        self._busy = True
        self.app.notify(t("dash.msg.checking"), "muted")
        for dot, detail in self.check_rows.values():
            dot.configure(fg=ui.COLORS["muted"])
            detail.configure(text="…", fg=ui.COLORS["muted"])

        def work():
            results = doctor.run_all()
            state, rows = dockerops.stack_state()
            docker = doctor.check_docker_cli()
            self._post(lambda: self._apply(results, state, rows, docker))

        threading.Thread(target=work, daemon=True).start()

    def _apply(self, results, state, rows, docker):
        if not self._alive():
            return
        self._busy = False
        for item in results:
            dot, detail = self.check_rows.get(item["key"], (None, None))
            if not dot:
                continue
            dot.configure(fg=ui.COLORS["ok"] if item["ok"] else ui.COLORS["bad"])
            detail.configure(text=item["detail"],
                             fg=ui.COLORS["muted"] if item["ok"] else ui.COLORS["bad"])

        self.stat_docker.value.configure(
            text=docker[1] if docker[0] else t("doctor.install.none"),
            fg=ui.COLORS["text"] if docker[0] else ui.COLORS["bad"])
        labels = {"healthy": ("dash.state.running", ui.COLORS["ok"]),
                  "starting": ("dash.state.starting", ui.COLORS["warn"]),
                  "partial": ("dash.state.partial", ui.COLORS["warn"]),
                  "stopped": ("dash.state.stopped", ui.COLORS["muted"])}
        key, color = labels.get(state, ("common.unknown", ui.COLORS["muted"]))
        self.stat_stack.value.configure(text=t(key), fg=color)
        version = paths.installed_version()
        installed = paths.is_installed()
        if version:
            label = f"v{version}"
        else:
            label = t("common.installed") if installed else t("common.not_installed")
        self.stat_version.value.configure(
            text=label, fg=ui.COLORS["text"] if installed else ui.COLORS["muted"])

        self._fill_table(rows)
        self.app.notify(t("dash.msg.checked"), "ok")

    def _fill_table(self, rows):
        self.tree.delete(*self.tree.get_children())
        state_keys = {"running": "dash.state.running", "exited": "dash.state.exited",
                      "created": "dash.state.created", "restarting": "dash.state.restarting"}
        for row in rows:
            state = t(state_keys[row["state"]]) if row["state"] in state_keys else (row["state"] or "—")
            health = {"healthy": "healthy", "unhealthy": "unhealthy",
                      "starting": "starting"}.get(row["health"], "")
            self.tree.insert("", "end", values=(
                row["service"], state, health, row["ports"], row["name"]))

    # ------------------------------------------------------------------
    def start_stack(self):
        if not paths.compose_path().is_file():
            self.app.notify(t("dash.msg.need_install"), "warn")
            self.app.goto("setup")
            return
        self.app.notify(t("dash.msg.starting"), "muted")

        def done(rc, out, err):
            self._post(lambda: self._after_action(rc, out, err, "dash.msg.started",
                                                  "dash.msg.start_failed"))

        dockerops.compose_async(["up", "-d", "--wait", "--wait-timeout", "900"],
                                timeout=1500, on_done=done)
        self.after(4000, self.refresh)

    def stop_stack(self):
        if not paths.compose_path().is_file():
            return
        self.app.notify(t("dash.msg.stopping"), "muted")

        def done(rc, out, err):
            self._post(lambda: self._after_action(rc, out, err, "dash.msg.stopped",
                                                  "dash.msg.stop_failed"))

        dockerops.compose_async(["stop"], timeout=300, on_done=done)
        self.after(3000, self.refresh)

    def _after_action(self, rc, out, err, ok_key, fail_key):
        if not self._alive():
            return
        if rc == 0:
            self.app.notify(t(ok_key), "ok")
        else:
            tail = (err or out or "").strip().splitlines()[-3:]
            self.app.notify(t(fail_key, detail=" / ".join(tail)), "bad")
        self.refresh()

    def open_web(self):
        url = dockerops.web_url()
        rows = dockerops.containers()
        running = any(r["service"] == "web" and r["state"] == "running" for r in rows)
        if not running and paths.compose_path().is_file():
            self.app.notify(t("dash.msg.web_starting"), "muted")
            dockerops.compose_async(["--profile", "web", "up", "-d", "web"], timeout=420)
            self.after(8000, lambda: webbrowser.open(url))
            self.after(9000, self.refresh)
            return
        webbrowser.open(url)

    def open_workspace(self):
        import os
        folder = paths.workspace_dir()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))
