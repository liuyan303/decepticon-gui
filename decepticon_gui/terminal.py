"""Embedded terminal: ConPTY -> VT screen -> Text widget.

The session (screen buffer + backend) is decoupled from the widget so a
theme or language switch can rebuild the page without killing a running
CLI process.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import font as tkfont

from . import conpty, paths, ui
from .dockerops import cli_command
from .i18n import t
from .vt import Screen

KEY_SEQUENCES = {
    "Up": "\x1b[A", "Down": "\x1b[B", "Right": "\x1b[C", "Left": "\x1b[D",
    "Home": "\x1b[H", "End": "\x1b[F", "Prior": "\x1b[5~", "Next": "\x1b[6~",
    "Insert": "\x1b[2~", "Delete": "\x1b[3~", "Return": "\r", "KP_Enter": "\r",
    "BackSpace": "\x7f", "Tab": "\t", "Escape": "\x1b",
    "F1": "\x1bOP", "F2": "\x1bOQ", "F3": "\x1bOR", "F4": "\x1bOS",
    "F5": "\x1b[15~", "F6": "\x1b[17~", "F7": "\x1b[18~", "F8": "\x1b[19~",
    "F9": "\x1b[20~", "F10": "\x1b[21~", "F11": "\x1b[23~", "F12": "\x1b[24~",
}


class TerminalSession:
    """Survives page rebuilds."""

    def __init__(self):
        self.screen = Screen(100, 30)
        self.backend = None
        self.backend_name = ""
        self.running = False

    def close(self):
        if self.backend:
            try:
                self.backend.close()
            except Exception:  # noqa: BLE001
                pass
        self.backend = None
        self.running = False


class TerminalFrame(tk.Frame):
    def __init__(self, parent, settings, session=None, on_status=None):
        super().__init__(parent, bg=ui.COLORS["term_bg"])
        self.settings = settings
        self.session = session or TerminalSession()
        self.on_status = on_status or (lambda text, tone: None)
        self._paint_job = None
        self._resize_job = None
        self._pump_job = None
        self._tags = {}
        self._inbox = []
        self._lock = threading.Lock()
        self._exit_code = None
        self._dirty = False

        size = int(settings.get("terminal_font_size", 11) or 11)
        self._set_fonts(size)

        self.text = tk.Text(
            self, bg=ui.COLORS["term_bg"], fg=ui.COLORS["term_fg"],
            insertwidth=0, bd=0, highlightthickness=0, relief="flat",
            wrap="none", padx=10, pady=8, takefocus=1, cursor="xterm",
            selectbackground=ui.COLORS["term_sel"],
            inactiveselectbackground=ui.COLORS["secondary"],
            font=self.font_normal,
        )
        self.text.pack(fill="both", expand=True)
        self.text.configure(state="disabled")
        self.text.tag_configure("cursor", background=ui.COLORS["accent"],
                                foreground=ui.COLORS["term_cursor_fg"])
        self.text.bind("<Key>", self._on_key)
        self.text.bind("<Control-c>", self._on_ctrl_c)
        self.text.bind("<Control-C>", self._on_ctrl_c)
        self.text.bind("<Control-v>", self._on_paste)
        self.text.bind("<Control-V>", self._on_paste)
        self.text.bind("<Button-1>", lambda e: self.text.focus_set())
        self.text.bind("<Configure>", self._on_configure)

        if self.session.backend:
            self.session.backend.on_data = self._on_data
            self.session.backend.on_exit = self._on_exit
            self.after(60, self._after_adopt)
        self._pump()

    # -- session plumbing -------------------------------------------
    @property
    def screen(self):
        return self.session.screen

    @property
    def backend(self):
        return self.session.backend

    @property
    def backend_name(self):
        return self.session.backend_name

    def running(self):
        return self.session.running

    def detach(self):
        """Called before the widget is destroyed by a rebuild."""
        if self.session.backend:
            self.session.backend.on_data = lambda data: None
            self.session.backend.on_exit = lambda code: None
        for job in (self._paint_job, self._resize_job, self._pump_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._paint_job = self._resize_job = self._pump_job = None

    def _after_adopt(self):
        self._resize_now(paint=False)
        if self.session.running:
            self.on_status(t("term.status.running", backend=self.session.backend_name), "ok")
        else:
            self.on_status(t("term.status.idle"), "muted")
        self._paint()

    # -- fonts -------------------------------------------------------
    def _set_fonts(self, size):
        family = ui.MONO_FONT
        self.font_normal = tkfont.Font(family=family, size=size)
        self.font_bold = tkfont.Font(family=family, size=size, weight="bold")
        self.font_italic = tkfont.Font(family=family, size=size, slant="italic")
        self.font_bold_italic = tkfont.Font(family=family, size=size,
                                            weight="bold", slant="italic")
        self._tags.clear()

    def set_font_size(self, size):
        size = max(7, min(20, int(size)))
        self.settings.set("terminal_font_size", size)
        self._set_fonts(size)
        self.text.configure(font=self.font_normal)
        self._tags.clear()
        self._resize_now()

    # -- backend -----------------------------------------------------
    def _resolve_command(self):
        override = (self.settings.get("terminal_shell") or "").strip()
        if override:
            return override
        cmd = cli_command()
        if cmd:
            return " ".join(f'"{c}"' if " " in c else c for c in cmd) \
                if isinstance(cmd, list) else cmd
        return None

    def start(self, command=None):
        if self.session.running:
            return
        command = command or self._resolve_command()
        if not command:
            self._show_message(t("term.no_cli"))
            self.on_status(t("term.status.idle"), "warn")
            return

        self._resize_now(paint=False)
        using_conpty = conpty.usable()
        backend_cls = conpty.ConPty if using_conpty else conpty.PipeProcess
        self.session.backend_name = "ConPTY" if using_conpty else "pipe"
        home = paths.decepticon_home()
        try:
            backend = backend_cls(
                command, cols=self.screen.cols, rows=self.screen.rows,
                cwd=str(home) if home.is_dir() else None, env=self._env(),
                on_data=self._on_data, on_exit=self._on_exit)
            backend.start()
        except Exception as exc:  # noqa: BLE001
            self.session.backend = None
            self._show_message(t("term.spawn_failed", err=exc))
            self.on_status(t("term.status.failed"), "bad")
            return
        self.session.backend = backend
        self.session.running = True
        self.text.focus_set()
        self.on_status(t("term.status.running", backend=self.session.backend_name), "ok")
        self._paint()

    def _env(self):
        import os
        env = dict(os.environ)
        env["DECEPTICON_HOME"] = str(paths.decepticon_home())
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        return env

    def stop(self):
        self.session.close()
        self.on_status(t("term.status.stopped"), "muted")

    # -- data flow ---------------------------------------------------
    def _on_data(self, data: bytes):
        """Called from the reader thread: never touch Tk here."""
        with self._lock:
            self._inbox.append(data)

    def _on_exit(self, code):
        self.session.running = False
        with self._lock:
            self._exit_code = code

    def _pump(self):
        """UI-thread drain of backend output."""
        self._pump_job = None
        if not self.winfo_exists():
            return
        with self._lock:
            data = b"".join(self._inbox)
            self._inbox.clear()
            exit_code = self._exit_code
            self._exit_code = None
        if data:
            self.screen.feed(data)
            for reply in self.screen.responses:
                if self.session.backend:
                    self.session.backend.write(reply)
            self.screen.responses.clear()
            self._dirty = True
        if exit_code is not None:
            self.on_status(t("term.status.exited", code=exit_code), "muted")
            self._dirty = True
        if self._dirty:
            self._dirty = False
            self._paint()
        self._pump_job = self.after(30, self._pump)

    def send(self, text: str):
        if self.session.backend:
            self.session.backend.write(text.encode("utf-8", "replace"))

    def _enter(self) -> str:
        """ConPTY expects CR, a plain pipe expects LF."""
        if isinstance(self.session.backend, conpty.PipeProcess):
            return "\n"
        return "\r"

    def send_line(self, text: str):
        self.send(text + self._enter())

    # -- painting ----------------------------------------------------
    def _schedule_paint(self):
        if self._paint_job is None:
            try:
                self._paint_job = self.after(16, self._paint)
            except tk.TclError:
                self._paint_job = None

    @staticmethod
    def _resolve_color(value, default):
        if value == "default":
            return default
        if isinstance(value, int):
            palette = ui.ansi_palette()
            return palette[value % len(palette)]
        return value

    def _paint(self):
        self._paint_job = None
        if not self.winfo_exists():
            return
        screen = self.screen
        rows, cols = screen.rows, screen.cols
        cx, cy = screen.cursor()
        text = self.text
        text.configure(state="normal")
        text.delete("1.0", "end")

        chunks = []
        for y in range(rows):
            row = screen.buffer[y]
            # trim trailing default-coloured blanks so lines do not carry
            # invisible padding into selections or the clipboard
            end = cols
            while end > 0:
                cell = row[end - 1]
                if cell.ch in ("", " ") and cell.bg == "default":
                    end -= 1
                else:
                    break
            if y == cy and cx >= end and screen.cursor_visible:
                end = min(cols, cx + 1)
            x = 0
            while x < end:
                cell = row[x]
                if cell.ch == "":
                    x += 1
                    continue
                if y == cy and x == cx and screen.cursor_visible:
                    chunks.append((cell.ch, ("cursor",)))
                    x += 1
                    continue
                key = cell.style_key()
                run = [cell.ch]
                nx = x + 1
                while nx < end:
                    nxt = row[nx]
                    if nxt.ch == "":
                        nx += 1
                        continue
                    if nxt.style_key() != key:
                        break
                    if y == cy and nx == cx and screen.cursor_visible:
                        break
                    run.append(nxt.ch)
                    nx += 1
                chunks.append(("".join(run), (self._tag_for(key),)))
                x = nx
            if y != rows - 1:
                chunks.append(("\n", ()))

        for content, tags in chunks:
            text.insert("end", content, tags)
        text.configure(state="disabled")
        screen.want_repaint = False

    def _tag_for(self, key):
        raw_fg, raw_bg, flags = key
        fg = self._resolve_color(raw_fg, ui.COLORS["term_fg"])
        bg = self._resolve_color(raw_bg, ui.COLORS["term_bg"])
        cache_key = (fg, bg, flags)
        name = f"c{abs(hash(cache_key)) % (10 ** 12)}"
        if name in self._tags:
            return name
        options = {}
        if raw_fg != "default":
            options["foreground"] = fg
        if raw_bg != "default":
            options["background"] = bg
        if flags & 8:
            options["underline"] = True
        if flags & 16:
            options["overstrike"] = True
        if flags & 2:
            options["foreground"] = ui.COLORS["muted"] if raw_fg == "default" else fg
        if flags & 1 and flags & 4:
            options["font"] = self.font_bold_italic
        elif flags & 1:
            options["font"] = self.font_bold
        elif flags & 4:
            options["font"] = self.font_italic
        self.text.tag_configure(name, **options)
        self._tags[name] = True
        return name

    # -- sizing ------------------------------------------------------
    def _on_configure(self, event=None):
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        self._resize_job = self.after(120, self._resize_now)

    def _resize_now(self, paint=True):
        self._resize_job = None
        if not self.text.winfo_exists():
            return
        width_px = self.text.winfo_width()
        height_px = self.text.winfo_height()
        if width_px < 120 or height_px < 80:
            # Not laid out yet (fresh page after a rebuild); try again shortly.
            retries = getattr(self, "_resize_retries", 0)
            if retries < 25:
                self._resize_retries = retries + 1
                self._resize_job = self.after(80, lambda: self._resize_now(paint))
            return
        self._resize_retries = 0
        width = max(80, width_px - 22)
        height = max(40, height_px - 18)
        char_w = max(1, self.font_normal.measure("M"))
        line_h = max(1, self.font_normal.metrics("linespace"))
        cols = max(20, width // char_w)
        rows = max(6, height // line_h)
        if (cols, rows) != (self.screen.cols, self.screen.rows):
            self.screen.resize(cols, rows)
            if self.session.backend:
                try:
                    self.session.backend.resize(cols, rows)
                except Exception:  # noqa: BLE001
                    pass
        if paint:
            self._schedule_paint()

    # -- input -------------------------------------------------------
    def _on_key(self, event):
        if event.state & 0x4 and event.keysym.lower() == "v":  # Ctrl+V
            return self._on_paste(event)

        seq = KEY_SEQUENCES.get(event.keysym)
        if event.keysym in ("Return", "KP_Enter"):
            seq = self._enter()
        if seq is None and event.char and event.char.isprintable():
            seq = event.char
        if seq is None:
            return "break"
        if event.state & 0x4 and len(seq) == 1:
            code = ord(seq.upper()) - 64
            if 0 <= code < 32:
                seq = chr(code)
        self.send(seq)
        return "break"

    def _on_paste(self, event=None):
        try:
            data = self.clipboard_get()
        except tk.TclError:
            return "break"
        self.send(data.replace("\r\n", "\r"))
        return "break"

    def _on_ctrl_c(self, event=None):
        try:
            selected = self.text.get("sel.first", "sel.last")
        except tk.TclError:
            selected = ""
        if selected:
            self.clipboard_clear()
            self.clipboard_append(selected)
            return "break"
        self.send("\x03")
        return "break"

    # -- helpers -----------------------------------------------------
    def _show_message(self, message):
        self.screen.reset()
        for line in message.splitlines():
            self.screen.feed(line.encode("utf-8"))
            self.screen.feed(b"\r\n")
        self._paint()

    def reset_screen(self):
        self.screen.reset()
        self._paint()

    def destroy(self):
        if self._pump_job:
            try:
                self.after_cancel(self._pump_job)
            except tk.TclError:
                pass
            self._pump_job = None
        super().destroy()
