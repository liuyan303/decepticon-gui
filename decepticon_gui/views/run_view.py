"""Run page: target in, CLI out, reports on the side."""

from __future__ import annotations

import os
import subprocess
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .. import dockerops, i18n, paths, ui
from ..i18n import t
from ..terminal import TerminalFrame

TEXT_SUFFIXES = {".txt", ".log", ".json", ".md", ".yaml", ".yml", ".csv",
                 ".xml", ".html", ".htm", ".py", ".sh", ".conf", ".ini"}
# what counts as a deliverable rather than a tool binary
REPORT_SUFFIXES = {".md", ".txt", ".log", ".json", ".html", ".htm", ".csv",
                   ".pdf", ".xml", ".yml", ".yaml"}
PROMPT_ENDS = (">", "❯", "?", "：", ":", "▌")


def _human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / 1048576:.1f} MB"


class RunView(tk.Frame):
    def __init__(self, parent, app, session=None):
        super().__init__(parent, bg=ui.COLORS["bg"])
        self.app = app
        self._probe_job = None
        self._report_job = None
        self._started_at = 0.0
        self._sent = False
        self._last_sig = ""
        self._last_change = 0.0
        self._files = {}
        self._build(session)

    # ------------------------------------------------------------------
    def _build(self, session):
        self.grid_columnconfigure(0, weight=1)

        head = tk.Frame(self, bg=ui.COLORS["bg"])
        head.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        box = tk.Frame(head, bg=ui.COLORS["bg"])
        box.pack(side="left")
        ui.label(box, t("run.title"), size=18, bold=True).pack(anchor="w")
        ui.label(box, t("run.subtitle"), size=9,
                 fg=ui.COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        form = ui.Card(self, padding=12)
        form.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        row1 = tk.Frame(form.body, bg=ui.COLORS["panel"])
        row1.pack(fill="x")
        ui.label(row1, t("run.target"), size=9, fg=ui.COLORS["muted"]).pack(side="left")
        self.target_box, self.target = ui.entry(row1)
        self.target_box.pack(side="left", fill="x", expand=True, padx=(10, 10), ipady=2)
        self.target.insert(0, self.app.settings.get("last_target", ""))

        self.mode = ttk.Combobox(row1, values=[t("run.mode.auto"), t("run.mode.plan")],
                                 state="readonly", width=10, font=ui.font(9))
        self.mode.set(t("run.mode.auto"))
        self.mode.pack(side="left", padx=(0, 10))
        ui.button(row1, t("run.start"), self.start_run, "primary").pack(side="left")

        row2 = tk.Frame(form.body, bg=ui.COLORS["panel"])
        row2.pack(fill="x", pady=(8, 0))
        ui.label(row2, t("run.notes"), size=9, fg=ui.COLORS["muted"]).pack(side="left")
        self.notes_box, self.notes = ui.entry(row2)
        self.notes_box.pack(side="left", fill="x", expand=True, padx=(10, 10), ipady=2)
        ui.button(row2, t("run.send"), self.send_objective, "secondary").pack(
            side="left", padx=(0, 6))
        ui.button(row2, t("common.stop"), self.stop_run, "secondary").pack(
            side="left", padx=(0, 6))
        ui.button(row2, t("run.clear"), self._clear, "ghost").pack(side="left", padx=(0, 6))
        ui.button(row2, "A+", lambda: self._font(1), "ghost", width=2).pack(side="left")
        ui.button(row2, "A-", lambda: self._font(-1), "ghost", width=2).pack(
            side="left", padx=(4, 6))
        ui.button(row2, t("run.external"), self._external, "ghost").pack(side="left")

        # body: terminal on the left, output files on the right ---------
        body = tk.Frame(self, bg=ui.COLORS["bg"])
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3, uniform="run")
        body.columnconfigure(1, weight=2, uniform="run")
        body.rowconfigure(0, weight=1)

        term_card = ui.Card(body, padding=0)
        term_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.term = TerminalFrame(term_card.body, self.app.settings, session=session,
                                  on_status=self._status)
        self.term.pack(fill="both", expand=True)

        reports = ui.Card(body, t("run.reports"), padding=12)
        reports.grid(row=0, column=1, sticky="nsew")
        toolbar = tk.Frame(reports.head, bg=ui.COLORS["panel"])
        toolbar.pack(side="right")
        ui.button(toolbar, t("common.refresh"), self.refresh_reports, "ghost").pack(
            side="left", padx=(0, 4))
        ui.button(toolbar, t("run.open_dir"), self._open_dir, "ghost").pack(side="left")

        cols = ("name", "size")
        self.tree = ttk.Treeview(reports.body, columns=cols, show="headings", height=7)
        self.tree.heading("name", text=t("run.col.file"))
        self.tree.heading("size", text="")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("size", width=60, anchor="e", stretch=False)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._preview_selected())
        self.tree.bind("<Double-1>", lambda e: self.open_selected())

        self.preview = tk.Text(reports.body, font=ui.font(8, mono=True),
                               bg=ui.COLORS["panel_alt"], fg=ui.COLORS["text"],
                               relief="flat", bd=0, wrap="word", padx=8, pady=6,
                               height=6)
        self.preview.pack(fill="both", expand=True, pady=(8, 0))
        self.preview.configure(state="disabled")

        self.status = ui.label(self, "", size=9, fg=ui.COLORS["muted"])
        self.status.grid(row=3, column=0, sticky="w", pady=(8, 0))

        self.grid_rowconfigure(2, weight=1)

    # ------------------------------------------------------------------
    def _status(self, text, tone="muted"):
        if not self.status.winfo_exists():
            return
        color = {"ok": ui.COLORS["ok"], "warn": ui.COLORS["warn"],
                 "bad": ui.COLORS["bad"]}.get(tone, ui.COLORS["muted"])
        self.status.configure(text=f"● {text}", fg=color)

    def on_show(self):
        self.target.focus_set()
        self.refresh_reports()
        if not self.term.running() and not self._sent:
            self._status(t("term.status.idle"), "muted")

    # ------------------------------------------------------------------
    def start_run(self):
        target = self.target.get().strip()
        if not target:
            self.app.notify(t("run.need_target"), "warn")
            self.target.focus_set()
            return
        if not dockerops.cli_command():
            self.app.notify(t("run.no_cli"), "warn")
            return

        self.app.settings.set("last_target", target)
        self._started_at = time.time()
        self._sent = False
        self.term.stop()
        self.term.reset_screen()
        self._status(t("run.starting"), "muted")
        self.term.start()
        if not self.term.running():
            self._status(t("term.status.failed"), "bad")
            return
        self._status(t("run.waiting"), "muted")
        self._last_sig, self._last_change = "", time.time()
        self._probe_deadline = time.time() + 300
        self._probe()
        self.refresh_reports()

    def send_objective(self):
        objective = self._objective_text()
        if not objective:
            self.app.notify(t("run.need_target"), "warn")
            return
        if not self.term.running():
            self.app.notify(t("run.no_cli"), "warn")
            return
        if self.mode.get() == t("run.mode.plan"):
            self.term.send_line("/mode plan")
            self.after(600, lambda: self.term.send_line(objective))
        else:
            self.term.send_line(objective)
        self._sent = True
        self.term.text.focus_set()
        self._status(t("run.sent"), "ok")
        self.app.notify(t("run.sent"), "ok")
        self._watch_reports()

    def _objective_text(self):
        target = self.target.get().strip()
        if not target:
            return ""
        notes = self.notes.get().strip()
        text = t("run.objective", target=target, notes=notes)
        return " ".join(text.split())

    def stop_run(self):
        self._cancel_probe()
        self._cancel_report_watch()
        self.term.stop()
        self._status(t("run.stopped"), "muted")

    def run_command(self, command):
        """Used by the Settings page (installer / onboard wizard)."""
        self.term.stop()
        self.term.reset_screen()
        self.term.start(command)
        if not self.term.running():
            self._status(t("term.status.failed"), "bad")
            return
        self._status(t("term.status.running", backend=self.term.backend_name), "ok")

    # ------------------------------------------------------------------
    def _probe(self):
        self._probe_job = None
        if not self.winfo_exists() or not self.term.running():
            return
        now = time.time()
        sig = self._screen_signature()
        if sig != self._last_sig:
            self._last_sig = sig
            self._last_change = now
        idle = now - self._last_change
        if idle > 1.5 and self._looks_like_prompt():
            self.send_objective()
            return
        if now > self._probe_deadline:
            self._status(t("run.wait_timeout"), "warn")
            return
        self._probe_job = self.after(600, self._probe)

    def _cancel_probe(self):
        if self._probe_job:
            try:
                self.after_cancel(self._probe_job)
            except tk.TclError:
                pass
            self._probe_job = None

    def _screen_signature(self):
        screen = self.term.screen
        lines = []
        for y in range(screen.rows):
            line = "".join(c.ch for c in screen.buffer[y]).rstrip()
            if line:
                lines.append(line)
        return "\n".join(lines[-6:])

    def _looks_like_prompt(self):
        lines = [ln for ln in self._screen_signature().splitlines() if ln.strip()]
        if not lines:
            return False
        return lines[-1].rstrip().endswith(PROMPT_ENDS)

    # ------------------------------------------------------------------
    def refresh_reports(self):
        folder = paths.workspace_dir()
        folder.mkdir(parents=True, exist_ok=True)
        cutoff = (self._started_at - 10) if self._started_at else (time.time() - 7 * 86400)
        entries = []
        try:
            for path in folder.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in REPORT_SUFFIXES:
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_mtime >= cutoff:
                    entries.append((stat.st_mtime, stat.st_size, path))
        except OSError:
            pass
        entries.sort(reverse=True)

        selected = self.tree.selection()
        keep = selected[0] if selected else None
        self.tree.delete(*self.tree.get_children())
        self._files.clear()
        for mtime, size, path in entries[:60]:
            rel = path.relative_to(folder).as_posix()
            item = self.tree.insert("", "end", values=(
                rel, _human_size(size)))
            self._files[item] = path
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
        elif not entries:
            self._set_preview(t("run.reports.empty"))

    def _watch_reports(self):
        self._cancel_report_watch()
        self.refresh_reports()
        self._report_job = self.after(4000, self._watch_reports)

    def _cancel_report_watch(self):
        if self._report_job:
            try:
                self.after_cancel(self._report_job)
            except tk.TclError:
                pass
            self._report_job = None

    def _preview_selected(self):
        item = self.tree.focus()
        path = self._files.get(item)
        if path:
            self._load_preview(path)

    def _load_preview(self, path: Path):
        try:
            stat = path.stat()
            if stat.st_size > 512 * 1024:
                hint = ("双击用系统程序打开" if i18n.translator.lang == "zh"
                        else "double-click to open externally")
                self._set_preview(f"{path.name}\n\n{_human_size(stat.st_size)} — {hint}")
                return
            if path.suffix.lower() in TEXT_SUFFIXES or stat.st_size < 200_000:
                text = path.read_text(encoding="utf-8", errors="replace")
            else:
                text = f"{path.name}\n\nbinary ({stat.st_size} bytes)"
        except OSError as exc:
            text = f"{path}\n\n{exc}"
        self._set_preview(text[:20000])

    def _set_preview(self, text):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("end", text)
        self.preview.configure(state="disabled")

    def open_selected(self):
        item = self.tree.focus()
        path = self._files.get(item)
        if path:
            os.startfile(str(path))

    def _open_dir(self):
        folder = paths.workspace_dir()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    # ------------------------------------------------------------------
    def _font(self, delta):
        size = int(self.app.settings.get("terminal_font_size", 11)) + delta
        self.term.set_font_size(size)

    def _clear(self):
        self.term.reset_screen()

    def _external(self):
        cmd = dockerops.cli_command()
        if not cmd:
            self.app.notify(t("run.no_cli"), "warn")
            return
        line = " ".join(f'"{c}"' if " " in c else c for c in cmd) \
            if isinstance(cmd, list) else cmd
        home = paths.decepticon_home()
        subprocess.Popen(["powershell", "-NoExit", "-Command", line],
                         cwd=str(home) if home.is_dir() else None,
                         creationflags=0x00000010)

    def detach(self):
        self._cancel_probe()
        self._cancel_report_watch()
        self.term.detach()
