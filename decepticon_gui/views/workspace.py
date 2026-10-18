"""Workspace browser: engagement files, reports, preview."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from .. import paths, ui
from ..i18n import t

TEXT_SUFFIXES = {".txt", ".log", ".json", ".md", ".yaml", ".yml", ".csv",
                 ".xml", ".html", ".py", ".sh", ".conf", ".ini"}


class WorkspaceView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=ui.COLORS["bg"])
        self.app = app
        self._paths = {}
        self._loaded = {}
        self._build()

    def _build(self):
        head = tk.Frame(self, bg=ui.COLORS["bg"])
        head.pack(fill="x", pady=(0, 12))
        box = tk.Frame(head, bg=ui.COLORS["bg"])
        box.pack(side="left")
        ui.label(box, t("ws.title"), size=18, bold=True).pack(anchor="w")
        self.root_label = ui.label(box, "", size=9, fg=ui.COLORS["muted"])
        self.root_label.pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(head, bg=ui.COLORS["bg"])
        actions.pack(side="right")
        ui.button(actions, t("common.refresh"), self.refresh, "ghost").pack(
            side="left", padx=(0, 6))
        ui.button(actions, t("ws.explorer"), self.open_dir, "secondary").pack(side="left")

        body = tk.Frame(self, bg=ui.COLORS["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2, uniform="w")
        body.columnconfigure(1, weight=3, uniform="w")
        body.rowconfigure(0, weight=1)

        left = ui.Card(body, t("ws.files"))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.tree = ttk.Treeview(left.body, show="tree", selectmode="browse")
        self.tree.column("#0", width=320)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double)

        right = ui.Card(body, t("ws.preview"))
        right.grid(row=0, column=1, sticky="nsew")
        self.preview = tk.Text(
            right.body, font=ui.font(9, mono=True), bg=ui.COLORS["panel_alt"],
            fg=ui.COLORS["text"], relief="flat", bd=0, wrap="none", padx=10,
            pady=8, insertbackground=ui.COLORS["text"])
        self.preview.pack(fill="both", expand=True)
        self.preview.configure(state="disabled")

    # ------------------------------------------------------------------
    def on_show(self):
        self.root_label.configure(text=str(paths.workspace_dir()))
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self._paths.clear()
        self._loaded.clear()
        root = paths.workspace_dir()
        root.mkdir(parents=True, exist_ok=True)
        self._populate("", root)
        self._loaded[""] = True

    def _populate(self, parent_item, directory):
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return
        for entry in entries:
            label = entry.name + ("/" if entry.is_dir() else "")
            item = self.tree.insert(parent_item, "end", text=label)
            self._paths[item] = entry
            if entry.is_dir():
                self.tree.insert(item, "end", text="…")

    def _on_open(self, _event=None):
        item = self.tree.focus()
        path = self._paths.get(item)
        if not path or not path.is_dir() or self._loaded.get(item):
            return
        for child in self.tree.get_children(item):
            self.tree.delete(child)
        self._populate(item, path)
        self._loaded[item] = True

    def _on_select(self, _event=None):
        item = self.tree.focus()
        path = self._paths.get(item)
        if not path or path.is_dir():
            return
        self._show_file(path)

    def _on_double(self, _event=None):
        item = self.tree.focus()
        path = self._paths.get(item)
        if not path:
            return
        if path.is_dir():
            self.tree.item(item, open=not self.tree.item(item, "open"))
            self._on_open()
        else:
            os.startfile(str(path))

    def _show_file(self, path):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        try:
            size = path.stat().st_size
            if size > 2 * 1024 * 1024:
                self.preview.insert("end", t("ws.too_large", name=path.name,
                                             size=f"{size / 1048576:.1f}"))
            elif path.suffix.lower() in TEXT_SUFFIXES or size < 262144:
                self.preview.insert("end", path.read_text(encoding="utf-8", errors="replace"))
            else:
                self.preview.insert("end", t("ws.binary", name=path.name, size=size))
        except OSError as exc:
            self.preview.insert("end", t("ws.read_failed", err=exc))
        self.preview.configure(state="disabled")

    def open_dir(self):
        folder = paths.workspace_dir()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))
