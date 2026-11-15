# SPDX-License-Identifier: GPL-3.0-or-later
"""The two kinds of transport the subsystem APIs are written against.

A :class:`Stream` carries bytes both ways (a serial port, an SSH channel, a socket): the MCU's and the Debug
Probe's text CLIs run over one. A :class:`Shell` runs commands and copies files (SSH): Linux on the device is
reached through one. Anything with these methods works; the library's own implementations are in this package.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..errors import CommandFailed


@runtime_checkable
class Stream(Protocol):
    """A duplex byte stream that is open from construction until :meth:`close`."""

    @property
    def name(self) -> str:
        """What errors and logs call it: a port path, ``host:/dev/ttyS1``."""
        ...

    def read(self, timeout: float) -> bytes:
        """Whatever arrives within ``timeout`` seconds (waits for the first byte, then takes what is there);
        ``b""`` when nothing came."""
        ...

    def write(self, data: bytes) -> None:
        """Send all of ``data``."""
        ...

    def reset_input(self) -> None:
        """Drop what has arrived but was not read yet."""
        ...

    def close(self) -> None:
        """Release the stream; closing twice is harmless."""
        ...


@dataclass(frozen=True)
class CommandResult:
    """A finished command: its exit code, stdout and stderr (decoded as UTF-8) and how long it took."""

    command: str
    code: int
    out: str
    err: str
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.code == 0

    def check(self) -> CommandResult:
        """The result itself, or :class:`~flipperone.errors.CommandFailed` for a non-zero exit code."""
        if not self.ok:
            raise CommandFailed(self)
        return self


@runtime_checkable
class Shell(Protocol):
    """Runs commands on a machine and copies files to and from it."""

    def run(self, command: str, timeout: float, on_line: Callable[[str], None] | None = None) -> CommandResult:
        """Run ``command`` (a shell command line). ``on_line`` gets each line of stdout as it arrives."""
        ...

    def open_stream(self, command: str) -> Stream:
        """Start ``command`` and return its stdin and stdout as a :class:`Stream` (no terminal: bytes pass as
        they are). Closing the stream ends the command."""
        ...

    def put(self, local: Path, remote: str) -> None:
        """Copy a local file to ``remote``."""
        ...

    def get(self, remote: str, local: Path) -> None:
        """Copy ``remote`` to a local file."""
        ...

    def close(self) -> None:
        """End the session."""
        ...
