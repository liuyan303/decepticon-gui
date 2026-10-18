"""A small VT/ANSI terminal screen model.

Covers the subset of escape sequences used by full-screen TUI programs
(alternate screen, cursor addressing, SGR colour, erase, scroll regions).
Not a complete emulator: no scrollback, no mouse reporting, no sixel.
"""

from __future__ import annotations

import codecs
import unicodedata

DEFAULT_FG = "default"
DEFAULT_BG = "default"


class Cell:
    __slots__ = ("ch", "fg", "bg", "bold", "dim", "italic", "underline", "inverse", "strike")

    def __init__(self, ch=" ", fg=DEFAULT_FG, bg=DEFAULT_BG):
        self.ch = ch
        self.fg = fg
        self.bg = bg
        self.bold = False
        self.dim = False
        self.italic = False
        self.underline = False
        self.inverse = False
        self.strike = False

    def copy_attrs(self, other):
        self.fg = other.fg
        self.bg = other.bg
        self.bold = other.bold
        self.dim = other.dim
        self.italic = other.italic
        self.underline = other.underline
        self.inverse = other.inverse
        self.strike = other.strike

    def reset(self):
        self.ch = " "
        self.fg = DEFAULT_FG
        self.bg = DEFAULT_BG
        self.bold = self.dim = self.italic = False
        self.underline = self.inverse = self.strike = False

    def style_key(self):
        fg = self.bg if self.inverse else self.fg
        bg = self.fg if self.inverse else self.bg
        flags = (1 if self.bold else 0) | (2 if self.dim else 0) | \
                (4 if self.italic else 0) | (8 if self.underline else 0) | \
                (16 if self.strike else 0)
        return (fg, bg, flags)


ERASE_TO_END, ERASE_TO_START, ERASE_ALL = 0, 1, 2


class Screen:
    def __init__(self, cols=100, rows=30):
        self.cols = max(10, cols)
        self.rows = max(4, rows)
        self.main = self._blank()
        self.alt = self._blank()
        self.buffer = self.main
        self.in_alt = False
        self.cx = 0
        self.cy = 0
        self.saved_cursor = (0, 0)
        self.attr = Cell()
        self.scroll_top = 0
        self.scroll_bottom = self.rows - 1
        self.wrap_pending = False
        self.cursor_visible = True
        self.title = ""
        self.want_repaint = True
        self.responses = []
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._state = "ground"
        self._seq = ""
        self._osc = ""

    # -- buffers -----------------------------------------------------
    def _blank(self):
        return [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]

    def resize(self, cols, rows):
        cols, rows = max(10, int(cols)), max(4, int(rows))
        if cols == self.cols and rows == self.rows:
            return
        def _resize(buf):
            out = [[Cell() for _ in range(cols)] for _ in range(rows)]
            for y in range(min(rows, self.rows)):
                for x in range(min(cols, self.cols)):
                    out[y][x] = buf[y][x]
            return out
        self.main = _resize(self.main)
        self.alt = _resize(self.alt)
        self.buffer = self.alt if self.in_alt else self.main
        self.cols, self.rows = cols, rows
        self.scroll_top, self.scroll_bottom = 0, rows - 1
        self.cx = min(self.cx, cols - 1)
        self.cy = min(self.cy, rows - 1)
        self.want_repaint = True

    def reset(self):
        self.main = self._blank()
        self.alt = self._blank()
        self.buffer = self.main
        self.in_alt = False
        self.cx = self.cy = 0
        self.scroll_top, self.scroll_bottom = 0, self.rows - 1
        self.attr = Cell()
        self.wrap_pending = False
        self.cursor_visible = True
        self.want_repaint = True

    # -- parsing -----------------------------------------------------
    def feed(self, data: bytes):
        text = self._decoder.decode(data)
        for ch in text:
            self._feed_char(ch)
        self.want_repaint = True

    def _feed_char(self, ch):
        state = self._state
        if state == "ground":
            self._ground(ch)
        elif state == "esc":
            self._escape(ch)
        elif state == "csi":
            if "@" <= ch <= "~":
                self._csi(self._seq, ch)
                self._state, self._seq = "ground", ""
            else:
                self._seq += ch
        elif state == "osc":
            if ch == "\x07":
                self._finish_osc()
            elif ch == "\x1b":
                self._state = "osc_esc"
            else:
                self._osc += ch
        elif state == "osc_esc":
            self._finish_osc()

    def _finish_osc(self):
        if self._osc.startswith("0;"):
            self.title = self._osc[2:]
        self._osc = ""
        self._state = "ground"

    def _ground(self, ch):
        if ch == "\x1b":
            self._state = "esc"
        elif ch == "\r":
            self.cx = 0
            self.wrap_pending = False
        elif ch == "\n":
            self._linefeed()
            self.wrap_pending = False
        elif ch == "\b":
            if self.cx > 0:
                self.cx -= 1
            self.wrap_pending = False
        elif ch == "\t":
            self.cx = min(self.cols - 1, (self.cx // 8 + 1) * 8)
            self.wrap_pending = False
        elif ch == "\x07":
            pass
        elif ch < " ":
            pass
        else:
            self._put(ch)

    def _put(self, ch):
        if self.wrap_pending:
            self.cx = 0
            self._linefeed()
            self.wrap_pending = False

        if unicodedata.combining(ch):
            prev = self.cx - 1 if self.cx else self.cols - 1
            row = self.buffer[self.cy]
            row[prev].ch += ch
            return

        width = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if width == 2 and self.cx >= self.cols - 1:
            self.cx = 0
            self._linefeed()

        cell = self.buffer[self.cy][self.cx]
        cell.ch = ch
        cell.copy_attrs(self.attr)
        if width == 2 and self.cx + 1 < self.cols:
            filler = self.buffer[self.cy][self.cx + 1]
            filler.ch = ""
            filler.copy_attrs(self.attr)

        self.cx += width
        if self.cx >= self.cols:
            self.cx = self.cols - 1
            self.wrap_pending = True

    def _linefeed(self):
        if self.cy == self.scroll_bottom:
            self._scroll_up(1)
        elif self.cy < self.rows - 1:
            self.cy += 1

    def _scroll_up(self, n=1):
        for _ in range(n):
            del self.buffer[self.scroll_top]
            self.buffer.insert(self.scroll_bottom, [Cell() for _ in range(self.cols)])

    def _scroll_down(self, n=1):
        for _ in range(n):
            del self.buffer[self.scroll_bottom]
            self.buffer.insert(self.scroll_top, [Cell() for _ in range(self.cols)])

    # -- escape ------------------------------------------------------
    def _escape(self, ch):
        self._state = "ground"
        if ch == "[":
            self._state, self._seq = "csi", ""
        elif ch == "]":
            self._state, self._osc = "osc", ""
        elif ch == "7":
            self.saved_cursor = (self.cx, self.cy)
        elif ch == "8":
            self.cx, self.cy = self.saved_cursor
        elif ch == "D":
            self._linefeed()
        elif ch == "M":
            if self.cy == self.scroll_top:
                self._scroll_down(1)
            elif self.cy > 0:
                self.cy -= 1
        elif ch == "E":
            self.cx = 0
            self._linefeed()
        elif ch == "c":
            self.reset()
        elif ch == "=" or ch == ">":
            pass

    def _csi(self, seq, final):
        private = seq.startswith("?")
        body = seq[1:] if private else seq
        parts = body.split(";") if body else []
        nums = []
        for p in parts:
            p = p.split(":")[0]
            try:
                nums.append(int(p) if p else 0)
            except ValueError:
                nums.append(0)

        def arg(i, default=1):
            return nums[i] if i < len(nums) and nums[i] else default

        if private:
            if final in ("h", "l"):
                on = final == "h"
                for n in nums:
                    if n == 1049 or n == 47 or n == 1047:
                        self._set_alt(on)
                    elif n == 25:
                        self.cursor_visible = on
                    elif n == 7:
                        pass
                return
            if final == "n":
                return
            return

        if final == "A":
            self.cy = max(self.scroll_top if self.cy >= self.scroll_top else 0,
                          self.cy - arg(0))
        elif final == "B":
            self.cy = min(self.rows - 1, self.cy + arg(0))
        elif final == "C":
            self.cx = min(self.cols - 1, self.cx + arg(0))
        elif final == "D":
            self.cx = max(0, self.cx - arg(0))
        elif final == "E":
            self.cy = min(self.rows - 1, self.cy + arg(0))
            self.cx = 0
        elif final == "F":
            self.cy = max(0, self.cy - arg(0))
            self.cx = 0
        elif final == "G" or final == "`":
            self.cx = min(self.cols - 1, arg(0) - 1)
        elif final in ("H", "f"):
            self.cy = min(self.rows - 1, arg(0) - 1)
            self.cx = min(self.cols - 1, arg(1) - 1)
        elif final == "d":
            self.cy = min(self.rows - 1, arg(0) - 1)
        elif final == "J":
            self._erase_display(nums[0] if nums else 0)
        elif final == "K":
            self._erase_line(nums[0] if nums else 0)
        elif final == "m":
            self._sgr(nums or [0])
        elif final == "L":
            self._insert_lines(arg(0))
        elif final == "M":
            self._delete_lines(arg(0))
        elif final == "P":
            self._delete_chars(arg(0))
        elif final == "@":
            self._insert_chars(arg(0))
        elif final == "X":
            self._erase_chars(arg(0))
        elif final == "S":
            self._scroll_up(arg(0))
        elif final == "T":
            self._scroll_down(arg(0))
        elif final == "r":
            self.scroll_top = max(0, arg(0) - 1)
            self.scroll_bottom = min(self.rows - 1, (nums[1] if len(nums) > 1 and nums[1] else self.rows) - 1)
            if self.scroll_bottom <= self.scroll_top:
                self.scroll_top, self.scroll_bottom = 0, self.rows - 1
            self.cx = self.cy = 0
        elif final == "s":
            self.saved_cursor = (self.cx, self.cy)
        elif final == "u":
            self.cx, self.cy = self.saved_cursor
        elif final == "n":
            if (nums[0] if nums else 0) == 6:
                self.responses.append(f"\x1b[{self.cy + 1};{self.cx + 1}R".encode())
        elif final == "c":
            self.responses.append(b"\x1b[?1;2c")
        self.wrap_pending = False

    def _set_alt(self, on):
        if on and not self.in_alt:
            self.in_alt = True
            self.alt = self._blank()
            self.buffer = self.alt
            self.cx = self.cy = 0
        elif not on and self.in_alt:
            self.in_alt = False
            self.buffer = self.main
            self.cx = self.cy = 0
        self.want_repaint = True

    def _erase_display(self, mode):
        if mode == 0:
            for x in range(self.cx, self.cols):
                self.buffer[self.cy][x] = self._blank_cell()
            for y in range(self.cy + 1, self.rows):
                self.buffer[y] = [self._blank_cell() for _ in range(self.cols)]
        elif mode == 1:
            for y in range(0, self.cy):
                self.buffer[y] = [self._blank_cell() for _ in range(self.cols)]
            for x in range(0, self.cx + 1):
                self.buffer[self.cy][x] = self._blank_cell()
        else:
            for y in range(self.rows):
                self.buffer[y] = [self._blank_cell() for _ in range(self.cols)]

    def _blank_cell(self):
        c = Cell()
        c.copy_attrs(self.attr)
        c.bg = self.attr.bg
        return c

    def _erase_line(self, mode):
        if mode == 0:
            for x in range(self.cx, self.cols):
                self.buffer[self.cy][x] = self._blank_cell()
        elif mode == 1:
            for x in range(0, self.cx + 1):
                self.buffer[self.cy][x] = self._blank_cell()
        else:
            self.buffer[self.cy] = [self._blank_cell() for _ in range(self.cols)]

    def _insert_lines(self, n):
        if not (self.scroll_top <= self.cy <= self.scroll_bottom):
            return
        for _ in range(n):
            del self.buffer[self.scroll_bottom]
            self.buffer.insert(self.cy, [self._blank_cell() for _ in range(self.cols)])

    def _delete_lines(self, n):
        if not (self.scroll_top <= self.cy <= self.scroll_bottom):
            return
        for _ in range(n):
            del self.buffer[self.cy]
            self.buffer.insert(self.scroll_bottom, [self._blank_cell() for _ in range(self.cols)])

    def _delete_chars(self, n):
        row = self.buffer[self.cy]
        for _ in range(min(n, self.cols - self.cx)):
            del row[self.cx]
            row.append(Cell())

    def _insert_chars(self, n):
        row = self.buffer[self.cy]
        for _ in range(min(n, self.cols - self.cx)):
            row.insert(self.cx, Cell())
            row.pop()

    def _erase_chars(self, n):
        for x in range(self.cx, min(self.cols, self.cx + n)):
            self.buffer[self.cy][x] = self._blank_cell()

    def _sgr(self, nums):
        i = 0
        while i < len(nums):
            n = nums[i]
            if n == 0:
                self.attr = Cell()
            elif n == 1:
                self.attr.bold = True
            elif n == 2:
                self.attr.dim = True
            elif n == 3:
                self.attr.italic = True
            elif n == 4:
                self.attr.underline = True
            elif n == 7:
                self.attr.inverse = True
            elif n == 9:
                self.attr.strike = True
            elif n == 22:
                self.attr.bold = self.attr.dim = False
            elif n == 23:
                self.attr.italic = False
            elif n == 24:
                self.attr.underline = False
            elif n == 27:
                self.attr.inverse = False
            elif n == 29:
                self.attr.strike = False
            elif 30 <= n <= 37:
                self.attr.fg = n - 30
            elif n == 39:
                self.attr.fg = DEFAULT_FG
            elif 40 <= n <= 47:
                self.attr.bg = n - 40
            elif n == 49:
                self.attr.bg = DEFAULT_BG
            elif 90 <= n <= 97:
                self.attr.fg = n - 90 + 8
            elif 100 <= n <= 107:
                self.attr.bg = n - 100 + 8
            elif n in (38, 48):
                target = "fg" if n == 38 else "bg"
                if i + 1 < len(nums):
                    mode = nums[i + 1]
                    if mode == 5 and i + 2 < len(nums):
                        setattr(self.attr, target, nums[i + 2] % 256)
                        i += 2
                    elif mode == 2 and i + 4 < len(nums):
                        r, g, b = nums[i + 2], nums[i + 3], nums[i + 4]
                        setattr(self.attr, target, f"#{r % 256:02x}{g % 256:02x}{b % 256:02x}")
                        i += 4
                    else:
                        i += 1
            i += 1

    # -- rendering helpers -------------------------------------------
    def visible_rows(self):
        return self.buffer

    def cursor(self):
        return self.cx, self.cy
