"""Minimal ConPTY wrapper (Windows 10 1809+) built on ctypes.

No third-party dependencies. If the host does not expose the
CreatePseudoConsole API, ``available()`` returns False and the caller
falls back to a plain pipe based runner.
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

IS_WINDOWS = os.name == "nt"

EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
INFINITE = 0xFFFFFFFF
ERROR_BROKEN_PIPE = 109

if IS_WINDOWS:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
else:  # pragma: no cover - the app targets Windows only
    kernel32 = None


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", STARTUPINFOW),
        ("lpAttributeList", wintypes.LPVOID),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


def _bind() -> bool:
    if not IS_WINDOWS or kernel32 is None:
        return False
    try:
        kernel32.CreatePseudoConsole.argtypes = [
            COORD,
            wintypes.HANDLE,
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        kernel32.CreatePseudoConsole.restype = ctypes.c_long
        kernel32.ResizePseudoConsole.argtypes = [wintypes.HANDLE, COORD]
        kernel32.ResizePseudoConsole.restype = ctypes.c_long
        kernel32.ClosePseudoConsole.argtypes = [wintypes.HANDLE]
        kernel32.ClosePseudoConsole.restype = None

        kernel32.CreatePipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(SECURITY_ATTRIBUTES),
            wintypes.DWORD,
        ]
        kernel32.CreatePipe.restype = wintypes.BOOL

        kernel32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPCWSTR,
            ctypes.POINTER(STARTUPINFOEXW),
            ctypes.POINTER(PROCESS_INFORMATION),
        ]
        kernel32.CreateProcessW.restype = wintypes.BOOL

        kernel32.InitializeProcThreadAttributeList.argtypes = [
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        kernel32.UpdateProcThreadAttribute.argtypes = [
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.c_size_t,
            wintypes.LPVOID,
            ctypes.c_size_t,
            wintypes.LPVOID,
            wintypes.LPVOID,
        ]
        kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
        kernel32.DeleteProcThreadAttributeList.argtypes = [wintypes.LPVOID]
        kernel32.DeleteProcThreadAttributeList.restype = None

        kernel32.ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        kernel32.ReadFile.restype = wintypes.BOOL
        kernel32.WriteFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        kernel32.WriteFile.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        return True
    except AttributeError:
        return False


_BOUND = _bind()


def available() -> bool:
    """True when the pseudo console API is usable on this host."""
    return bool(_BOUND)


def _env_block(env: dict[str, str]) -> ctypes.Array:
    entries = [f"{k}={v}" for k, v in env.items() if "=" not in k]
    return ctypes.create_unicode_buffer("\0".join(entries) + "\0\0")


_SELF_TEST = None


def self_test(timeout: float = 2.5) -> bool:
    """Spawn a throwaway console and confirm output actually comes back.

    The API can exist while the host still refuses to attach a console
    (locked-down sessions, some VMs), so presence alone is not enough.
    """
    if not available():
        return False
    chunks: list[bytes] = []
    proc = None
    marker = b"__conpty_ok__"
    try:
        proc = ConPty('cmd.exe /c echo __conpty_ok__', cols=80, rows=24,
                      on_data=chunks.append)
        proc.start()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if marker in b"".join(chunks):
                return True
            time.sleep(0.05)
        return False
    except Exception:  # noqa: BLE001
        return False
    finally:
        if proc:
            proc.close()


def usable() -> bool:
    """Cached answer to 'can we run an interactive terminal here?'."""
    global _SELF_TEST
    if _SELF_TEST is None:
        _SELF_TEST = self_test()
    return _SELF_TEST


class ConPty:
    """Spawns a console process attached to a pseudo console.

    ``on_data`` is invoked from a reader thread with raw bytes.
    ``on_exit`` is invoked once the child exits.
    """

    def __init__(self, command, cols=120, rows=32, cwd=None, env=None,
                 on_data=None, on_exit=None):
        if not _BOUND:
            raise OSError("ConPTY is not available on this system")
        self.command = command
        self.cols = max(20, int(cols))
        self.rows = max(5, int(rows))
        self.cwd = cwd
        self.env = dict(env or {})
        self.on_data = on_data
        self.on_exit = on_exit
        self.pid = None
        self.exit_code = None
        self._hpc = wintypes.HANDLE()
        self._proc = PROCESS_INFORMATION()
        self._in_write = None
        self._out_read = None
        self._attr_list = None
        self._closed = False
        self._read_thread = None
        self._wait_thread = None
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------
    def start(self):
        sa = SECURITY_ATTRIBUTES()
        sa.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
        sa.bInheritHandle = True
        sa.lpSecurityDescriptor = None

        in_read = wintypes.HANDLE()
        in_write = wintypes.HANDLE()
        out_read = wintypes.HANDLE()
        out_write = wintypes.HANDLE()
        if not kernel32.CreatePipe(ctypes.byref(in_read), ctypes.byref(in_write),
                                   ctypes.byref(sa), 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.CreatePipe(ctypes.byref(out_read), ctypes.byref(out_write),
                                   ctypes.byref(sa), 0):
            kernel32.CloseHandle(in_read)
            kernel32.CloseHandle(in_write)
            raise ctypes.WinError(ctypes.get_last_error())

        hr = kernel32.CreatePseudoConsole(
            COORD(self.cols, self.rows), in_read, out_write, 0,
            ctypes.byref(self._hpc))
        if hr != 0:
            for h in (in_read, in_write, out_read, out_write):
                kernel32.CloseHandle(h)
            raise OSError(f"CreatePseudoConsole failed: 0x{hr & 0xFFFFFFFF:08X}")

        # The pseudo console owns its ends of the pipes now.
        kernel32.CloseHandle(in_read)
        kernel32.CloseHandle(out_write)
        self._in_write = in_write
        self._out_read = out_read

        size = ctypes.c_size_t(0)
        kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not kernel32.InitializeProcThreadAttributeList(buffer, 1, 0,
                                                         ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        self._attr_list = buffer

        if not kernel32.UpdateProcThreadAttribute(
                buffer, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
                ctypes.cast(ctypes.byref(self._hpc), wintypes.LPVOID),
                ctypes.sizeof(wintypes.HANDLE), None, None):
            raise ctypes.WinError(ctypes.get_last_error())

        si = STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
        si.lpAttributeList = ctypes.cast(buffer, wintypes.LPVOID)

        cmdline = ctypes.create_unicode_buffer(self.command)
        env_block = None
        flags = EXTENDED_STARTUPINFO_PRESENT
        if self.env:
            env_block = _env_block(self.env)
            flags |= CREATE_UNICODE_ENVIRONMENT

        ok = kernel32.CreateProcessW(
            None, cmdline, None, None, True, flags, env_block,
            self.cwd, ctypes.byref(si), ctypes.byref(self._proc))
        if not ok:
            err = ctypes.get_last_error()
            kernel32.ClosePseudoConsole(self._hpc)
            self._hpc = wintypes.HANDLE()
            raise ctypes.WinError(err)

        self.pid = self._proc.dwProcessId
        kernel32.CloseHandle(self._proc.hThread)
        self._start_threads()
        return self.pid

    def _start_threads(self):
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        self._wait_thread = threading.Thread(target=self._wait_loop, daemon=True)
        self._wait_thread.start()

    def _read_loop(self):
        buf = ctypes.create_string_buffer(65536)
        read = wintypes.DWORD(0)
        while not self._closed:
            ok = kernel32.ReadFile(self._out_read, buf, 65536,
                                   ctypes.byref(read), None)
            if not ok or read.value == 0:
                break
            if self.on_data:
                self.on_data(buf.raw[: read.value])

    def _wait_loop(self):
        kernel32.WaitForSingleObject(self._proc.hProcess, INFINITE)
        code = wintypes.DWORD(0)
        kernel32.GetExitCodeProcess(self._proc.hProcess, ctypes.byref(code))
        self.exit_code = code.value
        if self.on_exit:
            self.on_exit(code.value)

    # -- io ----------------------------------------------------------
    def write(self, data: bytes):
        if self._closed or not self._in_write:
            return
        written = wintypes.DWORD(0)
        with self._lock:
            kernel32.WriteFile(self._in_write, data, len(data),
                               ctypes.byref(written), None)

    def resize(self, cols: int, rows: int):
        if self._closed or not self._hpc:
            return
        self.cols, self.rows = max(20, int(cols)), max(5, int(rows))
        kernel32.ResizePseudoConsole(self._hpc, COORD(self.cols, self.rows))

    def is_alive(self) -> bool:
        if not self._proc.hProcess:
            return False
        return kernel32.WaitForSingleObject(self._proc.hProcess, 0) == 0x102

    def close(self, terminate=True):
        if self._closed:
            return
        self._closed = True
        if terminate and self._proc.hProcess:
            kernel32.TerminateProcess(self._proc.hProcess, 1)
        if self._hpc:
            kernel32.ClosePseudoConsole(self._hpc)
            self._hpc = wintypes.HANDLE()
        for handle in (self._in_write, self._out_read):
            if handle:
                kernel32.CloseHandle(handle)
        self._in_write = self._out_read = None
        if self._proc.hProcess:
            kernel32.CloseHandle(self._proc.hProcess)
            self._proc.hProcess = None
        if self._attr_list is not None:
            kernel32.DeleteProcThreadAttributeList(self._attr_list)
            self._attr_list = None


class PipeProcess:
    """Fallback backend: plain pipes, no TTY. Used when ConPTY is missing."""

    def __init__(self, command, cols=120, rows=32, cwd=None, env=None,
                 on_data=None, on_exit=None):
        import subprocess

        self._subprocess = subprocess
        self.command = command
        self.cols, self.rows = cols, rows
        self.cwd, self.env = cwd, env
        self.on_data, self.on_exit = on_data, on_exit
        self.proc = None
        self.pid = None
        self.exit_code = None
        self._closed = False

    def start(self):
        creationflags = 0x08000000  # CREATE_NO_WINDOW
        self.proc = self._subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=self.env,
            stdin=self._subprocess.PIPE,
            stdout=self._subprocess.PIPE,
            stderr=self._subprocess.STDOUT,
            bufsize=0,
            creationflags=creationflags,
        )
        self.pid = self.proc.pid
        threading.Thread(target=self._read_loop, daemon=True).start()
        threading.Thread(target=self._wait_loop, daemon=True).start()
        return self.pid

    def _read_loop(self):
        while not self._closed:
            chunk = self.proc.stdout.read(4096) if self.proc.stdout else b""
            if not chunk:
                break
            if self.on_data:
                self.on_data(chunk)

    def _wait_loop(self):
        self.exit_code = self.proc.wait()
        if self.on_exit:
            self.on_exit(self.exit_code)

    def write(self, data: bytes):
        if self._closed or not self.proc or not self.proc.stdin:
            return
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def resize(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows

    def is_alive(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def close(self, terminate=True):
        self._closed = True
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except OSError:
                pass
