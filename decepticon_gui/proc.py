"""Subprocess helpers that never flash a console window."""

from __future__ import annotations

import os
import subprocess
import threading

CREATE_NO_WINDOW = 0x08000000


def _flags():
    return CREATE_NO_WINDOW if os.name == "nt" else 0


def run(cmd, cwd=None, env=None, timeout=30, input_text=None):
    """Run a command and capture output. Never raises on non-zero exit."""
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, env=env,
            input=input_text,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=_flags(),
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0] if isinstance(cmd, list) else cmd}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except OSError as exc:
        return 1, "", str(exc)


def run_async(cmd, cwd=None, env=None, timeout=60, on_done=None):
    def work():
        rc, out, err = run(cmd, cwd=cwd, env=env, timeout=timeout)
        if on_done:
            on_done(rc, out, err)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    return thread


class Stream:
    """Long running process whose output is pushed line by line."""

    def __init__(self, cmd, cwd=None, env=None, on_line=None, on_exit=None):
        self.cmd = cmd
        self.cwd = str(cwd) if cwd else None
        self.env = env
        self.on_line = on_line
        self.on_exit = on_exit
        self.proc = None
        self._stopped = False

    def start(self):
        self.proc = subprocess.Popen(
            self.cmd, cwd=self.cwd, env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", bufsize=1, creationflags=_flags(),
        )
        threading.Thread(target=self._pump, daemon=True).start()
        return self

    def _pump(self):
        try:
            for line in self.proc.stdout:
                if self._stopped:
                    break
                if self.on_line:
                    self.on_line(line.rstrip("\r\n"))
        except (OSError, ValueError):
            pass
        code = self.proc.wait()
        if self.on_exit:
            self.on_exit(code)

    def stop(self):
        self._stopped = True
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except OSError:
                pass

    def is_running(self):
        return bool(self.proc and self.proc.poll() is None)
