# SPDX-License-Identifier: GPL-3.0-or-later
"""A :class:`~flipperone.transport.base.Shell` over a Linux serial console: the CPU's console the Debug Probe bridges
(:data:`flipperone.probe.Role.CPU_CONSOLE`), where Flipper OS keeps ``user`` logged in. It needs no network, so it
works while SSH cannot: before the USB network is up, with the network stopped, in a test that takes it down.

A console is one terminal, not a channel per command:

- a command runs in a subshell of the logged-in shell, framed by two marker lines; its exit code comes back in the
  closing marker. stdout and stderr arrive as one stream (``err`` stays empty) and kernel messages printed to the
  console mix into it;
- nothing interactive: the command's stdin is the terminal, so one that reads it waits until its timeout, then gets
  Ctrl-C;
- one command line, no line breaks;
- no file copies and no streams (:meth:`put`, :meth:`get`, :meth:`open_stream` refuse): use SSH for those.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path

from .._text import strip_ansi
from ..errors import CommandTimeout, TransportError
from .base import CommandResult, Stream

PROMPT = re.compile(r"[$#] ?$")       # the end of the shell's prompt (user@host:~$, root's #)
BANNERS = ("fixed baud rate",)        # lines that are not the console's: the Debug Probe's, printed when a port opens
BEGIN = "__FLIPPERONE_BEGIN__"
END = "__FLIPPERONE_END__"
_END_LINE = re.compile(END + r"(\d+)$")
ETX = b"\x03"
READ_SLICE_S = 0.1


class SerialShell:
    """Commands on a Linux serial console over ``stream`` (an open :class:`~flipperone.transport.base.Stream`).
    ``ready_timeout_s``: how long :meth:`ready` waits for the prompt."""

    def __init__(self, stream: Stream, *, ready_timeout_s: float = 2.0,
                 clock: Callable[[], float] = time.monotonic):
        self.stream = stream
        self.ready_timeout_s = ready_timeout_s
        self._clock = clock

    @property
    def name(self) -> str:
        return self.stream.name

    def ready(self, attempts: int = 3) -> tuple[bool, bool]:
        """(a shell prompt answered, the console printed anything in answer). What waits unread (the probe's banner,
        the last lines of a shutdown) is dropped first; then Ctrl-C and Enter are sent and what comes is read until it
        goes quiet. The first try may land in other output, so it is tried ``attempts`` times. A silent console (the
        CPU off, waiting in a boot menu on the screen) answers ``(False, False)`` after one try."""
        printed = False
        for _ in range(attempts):
            self._read_quiet(0.3, quiet=0.2)
            self.stream.write(ETX + b"\r")
            text = "\n".join(line for line in _clean(self._read_quiet(self.ready_timeout_s, quiet=0.4)).split("\n")
                             if not any(banner in line for banner in BANNERS))
            printed = printed or bool(text.strip())
            if PROMPT.search(text.rstrip("\n").rstrip("\r")):
                return True, True
            if not text.strip():
                break
        return False, printed

    def run(self, command: str, timeout: float, on_line: Callable[[str], None] | None = None) -> CommandResult:
        """Run one command line (see the module's notes); ``timeout`` counts from the start. A console that shows no
        prompt: :class:`~flipperone.errors.TransportError`; no closing marker in time: Ctrl-C, then
        :class:`~flipperone.errors.CommandTimeout`."""
        if "\n" in command or "\r" in command:
            raise ValueError("a console command is one line")
        if not self.ready()[0]:
            raise TransportError(f"{self.name}: the console shows no shell prompt (booting, a login prompt, or off)")
        started = self._clock()
        self.stream.write(f"stty -echo; echo {BEGIN}; ( {command} ); echo {END}$?; stty echo\r".encode())
        lines: list[str] = []
        pending = b""
        begun = False
        deadline = started + timeout
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                self.stream.write(ETX)
                raise CommandTimeout(f"{self.name}: '{command}' did not finish within {timeout:g} s")
            pending += self.stream.read(min(remaining, READ_SLICE_S))
            *complete, pending = pending.split(b"\n")       # whole lines only: a sequence may span two reads
            for line in map(_clean, complete):
                if not begun:
                    begun = line == BEGIN
                    continue
                done = _END_LINE.search(line)
                if done:
                    before = line[:done.start()]          # output without a final newline
                    if before:
                        lines.append(before)
                        if on_line:
                            on_line(before)
                    out = "".join(f"{x}\n" for x in lines)
                    return CommandResult(command, int(done.group(1)), out, "", self._clock() - started)
                lines.append(line)
                if on_line:
                    on_line(line)

    def open_stream(self, command: str) -> Stream:
        raise TransportError("a serial console runs commands only: use SSH for a stream")

    def put(self, local: Path, remote: str) -> None:
        raise TransportError("a serial console runs commands only: use SSH to copy files")

    def get(self, remote: str, local: Path) -> None:
        raise TransportError("a serial console runs commands only: use SSH to copy files")

    def close(self) -> None:
        self.stream.close()

    def __enter__(self) -> SerialShell:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _read_quiet(self, timeout: float, quiet: float) -> bytes:
        """What arrives until ``quiet`` seconds pass without a byte, ``timeout`` at most."""
        deadline = self._clock() + timeout
        buf = bytearray()
        last = self._clock()
        while (now := self._clock()) < deadline and now - last < quiet:
            data = self.stream.read(min(deadline - now, READ_SLICE_S))
            if data:
                buf += data
                last = self._clock()
        return bytes(buf)


def _clean(data: bytes) -> str:
    """Console bytes as text: no ANSI sequences (colours, bracketed paste), ``\\n`` line ends."""
    return strip_ansi(data.decode("utf-8", errors="replace")).replace("\r\n", "\n").replace("\r", "")
