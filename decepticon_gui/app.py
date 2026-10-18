"""Main window, navigation, language and theme switching."""

from __future__ import annotations

import datetime
import threading
import tkinter as tk
from tkinter import messagebox

from . import __version__, i18n, paths, ui
from .i18n import t
from .settings import Settings
from .views.about import AboutView
from .views.dashboard import DashboardView
from .views.logs_view import LogsView
from .views.setup_view import SetupView
from .views.terminal_view import TerminalView
from .views.workspace import WorkspaceView

NAV = [
    ("dashboard", "nav.dashboard", "◉"),
    ("setup", "nav.setup", "⚙"),
    ("terminal", "nav.terminal", "▶"),
    ("workspace", "nav.workspace", "▤"),
    ("logs", "nav.logs", "☰"),
    ("about", "nav.about", "ⓘ"),
]


def _work_area(root):
    """Usable desktop size (excludes the taskbar) in Tk's coordinate space."""
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width > 200 and height > 200:
            return width, height
    except Exception:  # noqa: BLE001
        pass
    return root.winfo_screenwidth(), root.winfo_screenheight() - 60


class App(tk.Tk):
    def __init__(self, start_page=None):
        super().__init__()
        self.settings = Settings()
        self._log_listeners = []
        self._notify_job = None
        self.current_page = start_page or self.settings.get("last_page", "dashboard")
        self.views = {}
        self.nav_items = {}

        self._apply_language(self.settings.get("language", "auto"), remember=False)
        self._apply_theme(self.settings.get("theme", "auto"), remember=False)
        ui.init_style(self)

        self.title("Decepticon GUI")
        area_w, area_h = _work_area(self)
        scale = max(1.0, self.winfo_fpixels("1i") / 96.0)
        saved = self.settings.get("window", "")
        if saved:
            try:
                size = saved.split("+")[0]
                width, height = (int(v) for v in size.split("x"))
                if width > area_w - 30 or height > area_h - 50:
                    saved = ""
            except ValueError:
                saved = ""
        if saved:
            self.geometry(saved)
        else:
            width = min(int(1180 * scale), area_w - 80)
            height = min(int(840 * scale), area_h - 70)
            x = max(0, (area_w - width) // 2)
            y = max(0, (area_h - height) // 3)
            self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(int(960 * scale), int(600 * scale))
        self.configure(bg=ui.COLORS["bg"])

        self._build_shell()
        self._create_views()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.goto(self.current_page, remember=False)
        self.after(200, self._first_run_hint)
        threading.Thread(target=self._warm_conpty, daemon=True).start()

    # -- chrome ------------------------------------------------------
    def _build_shell(self):
        self._build_sidebar()
        self._build_content()
        self._build_statusbar()

    def _build_sidebar(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        bar = tk.Frame(self, bg=ui.COLORS["sidebar"], width=210)
        bar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        bar.pack_propagate(False)
        tk.Frame(self, bg=ui.COLORS["border"], width=1).grid(
            row=0, column=1, rowspan=2, sticky="ns")

        brand = tk.Frame(bar, bg=ui.COLORS["sidebar"])
        brand.pack(fill="x", padx=18, pady=(22, 18))
        tk.Label(brand, text="Decepticon", font=ui.font(14, True),
                 fg=ui.COLORS["text"], bg=ui.COLORS["sidebar"]).pack(anchor="w")
        tk.Label(brand, text=t("app.subtitle"), font=ui.font(8),
                 fg=ui.COLORS["muted"], bg=ui.COLORS["sidebar"]).pack(anchor="w", pady=(2, 0))

        self.nav_items = {}
        for key, title_key, icon in NAV:
            row = tk.Frame(bar, bg=ui.COLORS["sidebar"], cursor="hand2")
            row.pack(fill="x", padx=10, pady=1)
            icon_label = tk.Label(row, text=icon, font=ui.font(10),
                                  bg=ui.COLORS["sidebar"], fg=ui.COLORS["muted"], width=3)
            icon_label.pack(side="left", pady=8)
            text_label = tk.Label(row, text=t(title_key), font=ui.font(10),
                                  bg=ui.COLORS["sidebar"], fg=ui.COLORS["text"], anchor="w")
            text_label.pack(side="left", fill="x", expand=True)
            for widget in (row, icon_label, text_label):
                widget.bind("<Button-1>", lambda e, k=key: self.goto(k))
                widget.bind("<Enter>", lambda e, r=row: self._hover(r, True))
                widget.bind("<Leave>", lambda e, r=row: self._hover(r, False))
            self.nav_items[key] = (row, icon_label, text_label)

        footer = tk.Frame(bar, bg=ui.COLORS["sidebar"])
        footer.pack(side="bottom", fill="x", padx=14, pady=14)
        row = tk.Frame(footer, bg=ui.COLORS["sidebar"])
        row.pack(fill="x")
        self.lang_btn = tk.Button(
            row, text="English" if i18n.translator.lang == "zh" else "中文",
            command=self.toggle_language, font=ui.font(8),
            bg=ui.COLORS["secondary"], fg=ui.COLORS["text"], relief="flat", bd=0,
            activebackground=ui.COLORS["secondary_active"],
            activeforeground=ui.COLORS["text"], cursor="hand2", padx=8, pady=4)
        self.lang_btn.pack(side="left")
        theme_label = (t("app.theme.light") if ui.current_theme() == "dark"
                       else t("app.theme.dark"))
        self.theme_btn = tk.Button(
            row, text=theme_label, command=self.toggle_theme, font=ui.font(8),
            bg=ui.COLORS["secondary"], fg=ui.COLORS["text"], relief="flat", bd=0,
            activebackground=ui.COLORS["secondary_active"],
            activeforeground=ui.COLORS["text"], cursor="hand2", padx=8, pady=4)
        self.theme_btn.pack(side="left", padx=(6, 0))

        version = paths.installed_version()
        self.footer_label = tk.Label(
            footer, text=f"v{__version__}", font=ui.font(8),
            fg=ui.COLORS["muted"], bg=ui.COLORS["sidebar"], anchor="w", justify="left")
        self.footer_label.pack(anchor="w", pady=(8, 0))
        if version != "not installed":
            self.footer_label.configure(text=f"v{__version__}  ·  Decepticon v{version}")

    def _hover(self, row, inside):
        active = getattr(row, "_active", False)
        bg = ui.COLORS["hover"] if inside or active else ui.COLORS["sidebar"]
        row.configure(bg=bg)
        for child in row.winfo_children():
            child.configure(bg=bg)

    def _build_content(self):
        self.content = tk.Frame(self, bg=ui.COLORS["bg"])
        self.content.grid(row=0, column=2, sticky="nsew", padx=22, pady=(18, 0))

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=ui.COLORS["bg"], height=34)
        bar.grid(row=1, column=2, sticky="ew", padx=22, pady=(0, 10))
        ui.separator(bar, pady=0).pack(fill="x", pady=(4, 6))
        self.status = tk.Label(bar, text="", font=ui.font(9),
                               fg=ui.COLORS["muted"], bg=ui.COLORS["bg"], anchor="w")
        self.status.pack(side="left")

    # -- views -------------------------------------------------------
    def _create_views(self, session=None):
        self.views = {
            "dashboard": DashboardView(self.content, self),
            "setup": SetupView(self.content, self),
            "terminal": TerminalView(self.content, self, session=session),
            "workspace": WorkspaceView(self.content, self),
            "logs": LogsView(self.content, self),
            "about": AboutView(self.content, self),
        }
        for view in self.views.values():
            view.place(relx=0, rely=0, relwidth=1, relheight=1)

    def goto(self, key, remember=True):
        view = self.views.get(key)
        if not view:
            return
        for name, (row, icon_label, text_label) in self.nav_items.items():
            active = name == key
            row._active = active
            bg = ui.COLORS["accent_soft"] if active else ui.COLORS["sidebar"]
            row.configure(bg=bg)
            icon_label.configure(bg=bg,
                                 fg=ui.COLORS["accent"] if active else ui.COLORS["muted"])
            text_label.configure(bg=bg,
                                 fg=ui.COLORS["accent_dark"] if active else ui.COLORS["text"],
                                 font=ui.font(10, active))
        view.tkraise()
        self.current_page = key
        if hasattr(view, "on_show"):
            try:
                view.on_show()
            except Exception as exc:  # noqa: BLE001
                self.notify(t("app.page_error", err=exc), "bad")
        if remember:
            self.settings.set("last_page", key)

    # -- language / theme -------------------------------------------
    def _apply_language(self, value, remember=True):
        if value in ("zh", "en"):
            i18n.translator.set(value)
        else:
            i18n.translator.set(i18n.system_language())
        if remember:
            self.settings.set("language", value)

    def _apply_theme(self, value, remember=True):
        name = value if value in ("light", "dark") else ui.preferred_theme()
        ui.set_theme(name)
        if remember:
            self.settings.set("theme", value)

    def toggle_language(self):
        target = "en" if i18n.translator.lang == "zh" else "zh"
        self._apply_language(target)
        self.rebuild()

    def toggle_theme(self):
        target = "dark" if ui.current_theme() == "light" else "light"
        self._apply_theme(target)
        self.rebuild()

    def rebuild(self):
        """Recreate the UI after a language or theme change."""
        page = self.current_page
        session = None
        terminal = self.views.get("terminal")
        if terminal:
            terminal.term.detach()
            session = terminal.term.session
        logs = self.views.get("logs")
        if logs and hasattr(logs, "detach"):
            logs.detach()

        self._log_listeners.clear()
        for child in self.winfo_children():
            child.destroy()
        self.views = {}
        ui.init_style(self)
        self.configure(bg=ui.COLORS["bg"])
        self._build_shell()
        self._create_views(session)
        self.goto(page, remember=False)

    # -- misc --------------------------------------------------------
    def notify(self, message, tone="muted"):
        color = {"ok": ui.COLORS["ok"], "warn": ui.COLORS["warn"],
                 "bad": ui.COLORS["bad"]}.get(tone, ui.COLORS["muted"])
        if getattr(self, "status", None) and self.status.winfo_exists():
            self.status.configure(text=message, fg=color)
        self.log(message)
        if self._notify_job:
            try:
                self.after_cancel(self._notify_job)
            except tk.TclError:
                pass
        self._notify_job = self.after(
            9000, lambda: self.status.configure(text="")
            if self.status.winfo_exists() else None)

    def log(self, message):
        line = f"[{datetime.datetime.now():%H:%M:%S}] {message}"
        for listener in list(self._log_listeners):
            try:
                listener(line)
            except Exception:  # noqa: BLE001
                pass

    def add_log_listener(self, callback):
        self._log_listeners.append(callback)

    def run_in_terminal(self, command):
        self.goto("terminal")
        self.views["terminal"].run_command(command)

    @staticmethod
    def _warm_conpty():
        from . import conpty
        conpty.usable()

    def _first_run_hint(self):
        if not paths.is_installed():
            self.notify(t("app.first_run"), "warn")

    def _on_close(self):
        try:
            self.settings.set("window", self.geometry())
            terminal = self.views.get("terminal")
            if terminal and terminal.term.running():
                terminal.term.stop()
        finally:
            self.destroy()


def _enable_dpi_awareness():
    """Render at native resolution on scaled displays (125% / 150%)."""
    import sys

    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001 - Windows 8.1 以下没有 shcore
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def _crash_log(exc: BaseException) -> str:
    import traceback

    path = paths.appdata_dir() / "crash.log"
    try:
        path.write_text(
            "Decepticon GUI crash\n"
            f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
            + "".join(traceback.format_exception(exc)),
            encoding="utf-8")
    except OSError:
        pass
    return str(path)


def _dump_environment(path: str) -> None:
    """Diagnostics for a frozen build (no console to print to)."""
    import platform
    import sys
    import tkinter
    from tkinter import ttk

    root = tkinter.Tk()
    style = ttk.Style(root)
    lines = [
        f"python {sys.version}",
        f"platform {platform.platform()}",
        f"tcl {root.tk.call('info', 'patchlevel')}",
        f"frozen {getattr(sys, 'frozen', False)}",
        f"theme {ui.current_theme()}",
        f"language {i18n.translator.lang}",
        f"palette_keys {sorted(ui.COLORS)}",
        "colors " + ", ".join(f"{k}={v}" for k, v in sorted(ui.COLORS.items())),
        f"ttk themes {style.theme_names()}",
        f"appdata {paths.appdata_dir()}",
        f"home {paths.decepticon_home()}",
    ]
    root.destroy()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Decepticon GUI")
    parser.add_argument("--page", default=None,
                        help="dashboard | setup | terminal | workspace | logs | about")
    parser.add_argument("--dump-env", default=None,
                        help="write environment diagnostics to this file and exit")
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        print("Decepticon GUI targets Windows 10/11 (ConPTY + Docker Desktop).")
    _enable_dpi_awareness()
    if args.dump_env:
        _dump_environment(args.dump_env)
        return
    try:
        App(start_page=args.page).mainloop()
    except Exception as exc:  # noqa: BLE001 - last resort, keep a trace for bug reports
        log_path = _crash_log(exc)
        try:
            messagebox.showerror(
                "Decepticon GUI",
                f"Startup failed://n{exc}//n//nLog: {log_path}")
        except Exception:  # noqa: BLE001
            pass
        raise
