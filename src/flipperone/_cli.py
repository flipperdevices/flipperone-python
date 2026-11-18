# SPDX-License-Identifier: GPL-3.0-or-later
"""The line-oriented shell the MCU and the Debug Probe firmwares share (flipperone-mcu-firmware, lib/cli/shell/):

- the prompt is ``<name>>: `` (``control>: ``, ``debug_probe>: ``) and always follows ``\\r\\n``;
- only CR submits a line (LF is dropped); the line is echoed, then ``\\r\\n``, the output, ``\\r\\n`` and the prompt;
- only printable ASCII is accepted;
- Ctrl-C (ETX) stops a command that keeps printing; at the prompt it prints ``^C`` and a new prompt, which brings
  a session to a known state.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from .errors import CliError, CommandNotFound, FlipperOneError, PortNotFound, SyncTimeout, UsageError
from .transport.base import Stream

PROMPT = b">: "
CR = b"\r"
ETX = b"\x03"
READ_SLICE_S = 0.1

ANSI_CSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_PROMPT_TAIL = re.compile(r"\n?[^\n]*>: $")
_NOT_FOUND = re.compile(r"could not find command `([^`]*)`")

wire = logging.getLogger("flipperone.wire")
log = logging.getLogger("flipperone.cli")      # DEBUG: one line per command (the device, the command, time, size)

Connect = Callable[[], Stream]


def strip_ansi(text: str) -> str:
    """``text`` without ANSI escape sequences (colours, cursor moves)."""
    return ANSI_CSI.sub("", text)


@dataclass(frozen=True)
class Result:
    """A command's reply: everything the device sent (``raw``) and the output as text (``text``: no ANSI, no echo,
    no prompt, ``\\n`` line ends)."""

    command: str
    raw: bytes
    text: str

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


def check_line(line: str) -> None:
    if not line or any(not 0x20 <= ord(c) <= 0x7E for c in line):
        raise ValueError(f"a command line must be non-empty printable ASCII: {line!r}")


def clean(raw: bytes, command: str | None) -> str:
    text = strip_ansi(raw.decode("ascii", errors="replace")).replace("\r\n", "\n").replace("\r", "")
    text = _PROMPT_TAIL.sub("", text)
    if command is not None:
        if text.startswith(command + "\n"):
            text = text[len(command) + 1:]
        elif text == command:
            text = ""
    return text.strip("\n")


class RawSession:
    """Bytes in and out of the CLI's stream while the shell is set aside (:meth:`CliDevice.raw_session`)."""

    def __init__(self, stream: Stream):
        self._stream = stream

    def read(self, timeout: float) -> bytes:
        data = self._stream.read(timeout)
        if data:
            wire.debug("RX %r", data)
        return data

    def write(self, data: bytes) -> None:
        wire.debug("TX %r", data)
        self._stream.write(data)


class CliDevice:
    """A text CLI over a :class:`~flipperone.transport.base.Stream`: the session is opened at construction and
    brought to the prompt. ``connect`` is a stream, or a callable returning a new one (then :meth:`reconnect` can
    open it again after the device restarted)."""

    def __init__(self, connect: Stream | Connect, *, timeout_s: float = 2.0, sync_timeout_s: float = 3.0,
                 settle_s: float = 0.3, reconnect_timeout_s: float = 20.0,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.timeout_s = timeout_s
        self.sync_timeout_s = sync_timeout_s
        self.settle_s = settle_s
        self.reconnect_timeout_s = reconnect_timeout_s
        self._connect: Connect | None = None if isinstance(connect, Stream) else connect
        self._given: Stream | None = connect if isinstance(connect, Stream) else None
        self._sleep = sleep
        self._clock = clock
        self._stream: Stream | None = None
        self.open()

    # -- session -----------------------------------------------------------------------------------

    @property
    def name(self) -> str:
        """The stream's name (a port path), for messages."""
        return self._stream.name if self._stream is not None else "(closed)"

    @property
    def is_open(self) -> bool:
        return self._stream is not None

    def open(self) -> None:
        """Open the stream (when closed) and bring the CLI to its prompt."""
        if self._stream is None:
            if self._connect is not None:
                self._stream = self._connect()
            elif self._given is not None:
                self._stream, self._given = self._given, None
            else:
                raise CliError("the stream was given, not a way to open one: it cannot be opened again")
        self._sleep(self.settle_s)      # a CDC port starts its session on DTR and prints a banner
        self._stream.reset_input()
        self.sync()

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def __enter__(self) -> CliDevice:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def reconnect(self, timeout: float | None = None) -> None:
        """Close, then open again as soon as the stream can be opened (after the device restarted), within
        ``timeout`` seconds (default ``reconnect_timeout_s``)."""
        if self._connect is None:
            raise CliError(f"{self.name}: given a stream, not a way to open one; open a new one and pass it")
        timeout = self.reconnect_timeout_s if timeout is None else timeout
        deadline = self._clock() + timeout
        self.close()
        last: FlipperOneError | None = None
        while self._clock() < deadline:
            try:
                self.open()
                return
            except FlipperOneError as e:      # not there yet, or there but still starting
                last = e
                self.close()
                self._sleep(0.5)
        raise PortNotFound(f"the CLI did not come back within {timeout:g} s" + (f": {last}" if last else ""))

    # -- commands ----------------------------------------------------------------------------------

    def run(self, line: str, timeout: float | None = None) -> Result:
        """Run one command line and return its reply once the prompt is back."""
        started = self._clock()
        self._send(line)
        try:
            raw = self._read_until(PROMPT, timeout or self.timeout_s, f"the prompt after '{line}'")
        except Exception as e:
            log.debug("%s: %s -> %s: %s", type(self).__name__, line, type(e).__name__, e)
            raise
        text = clean(raw, line)
        log.debug("%s: %s -> %.2f s, %d B", type(self).__name__, line, self._clock() - started, len(text))
        m = _NOT_FOUND.search(text)
        if m:
            raise CommandNotFound(f"{self.name}: could not find command `{m.group(1)}`")
        return Result(line, raw, text)

    def stream(self, line: str, seconds: float) -> Result:
        """Run a command that keeps printing until stopped, collect for ``seconds``, then stop it with Ctrl-C."""
        self._send(line)
        raw = self._read_for(seconds)
        self._write(ETX)
        raw += self._read_until(PROMPT, self.timeout_s, f"the prompt after stopping '{line}'")
        text = clean(raw, line)
        log.debug("%s: %s (for %g s) -> %d B", type(self).__name__, line, seconds, len(text))
        return Result(line, raw, text)

    def watch(self, line: str, handler: Callable[[str], bool], timeout: float) -> bool:
        """Run a command that keeps printing and give each line to ``handler`` as it arrives, until the handler
        returns True or ``timeout`` passes; then stop the command and wait for the prompt. Every read slice without
        a complete line calls ``handler("")`` (for the handler's own clocks). Returns whether the handler stopped
        it (False: the timeout did)."""
        self._send(line)
        deadline = self._clock() + timeout
        pending, done = b"", False
        while not done and self._clock() < deadline:
            pending += self._read(min(max(deadline - self._clock(), 0.0), READ_SLICE_S))
            *lines, pending = pending.split(b"\n")
            if not lines and handler(""):
                done = True
            for raw_line in lines:
                if handler(strip_ansi(raw_line.decode("ascii", errors="replace")).strip("\r ")):
                    done = True
                    break
        self._write(ETX)
        self._read_until(PROMPT, self.timeout_s, f"the prompt after stopping '{line}'")
        log.debug("%s: %s (watched, %g s at most) -> %s", type(self).__name__, line, timeout,
                  "the handler stopped it" if done else "timed out")
        return done

    @contextmanager
    def raw_session(self, line: str | None = None) -> Iterator[RawSession]:
        """Set the shell aside: send ``line`` (a command that switches to a binary protocol, such as ``rpc``) and
        hand over the stream's bytes; on leaving, the CLI is brought back to its prompt (Ctrl-C) whatever happened."""
        stream = self._require()
        if line is not None:
            self._send(line)
        try:
            yield RawSession(stream)
        finally:
            self._sleep(0.3)
            self.sync()

    def sync(self, timeout: float | None = None) -> str:
        """Ctrl-C and wait for the prompt: a known state whatever the device was doing."""
        self._write(ETX)
        return clean(self._read_until(PROMPT, timeout or self.sync_timeout_s, "the prompt after Ctrl-C"), None)

    def send_line(self, line: str) -> None:
        """Send a command line without waiting for its reply (a command after which the device restarts)."""
        self._send(line)

    # -- helpers for subclasses --------------------------------------------------------------------

    def _text(self, line: str, timeout: float | None = None) -> str:
        text = self.run(line, timeout).text
        if any(t.startswith(("Usage:", "usage:")) for t in text.splitlines()):
            raise UsageError(f"'{line}': the device answered with its usage text:\n{text}")
        return text

    def _send(self, line: str) -> None:
        check_line(line)
        self._write(line.encode("ascii") + CR)

    def _write(self, data: bytes) -> None:
        wire.debug("TX %r", data)
        self._require().write(data)

    def _read(self, timeout: float) -> bytes:
        data = self._require().read(timeout)
        if data:
            wire.debug("RX %r", data)
        return data

    def _read_until(self, marker: bytes, timeout: float, what: str) -> bytes:
        deadline = self._clock() + timeout
        buf = bytearray()
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise SyncTimeout(f"{self.name}: no answer within {timeout:g} s waiting for {what}"
                                  + (f"; received {bytes(buf)!r}" if buf else ""), bytes(buf))
            buf += self._read(min(remaining, READ_SLICE_S))
            if buf.endswith(marker):
                return bytes(buf)

    def _read_for(self, seconds: float) -> bytes:
        deadline = self._clock() + seconds
        buf = bytearray()
        while (remaining := deadline - self._clock()) > 0:
            buf += self._read(min(remaining, READ_SLICE_S))
        return bytes(buf)

    def _require(self) -> Stream:
        if self._stream is None:
            raise CliError("the CLI session is closed")
        return self._stream
