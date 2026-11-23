# SPDX-License-Identifier: GPL-3.0-or-later
"""The MCU's log as it is printed, line by line, each with this machine's time (the Debug Probe's MCU log port,
:data:`flipperone.probe.Role.MCU_LOG`; output only).

The MCU's own timestamps (milliseconds since its start, first on every line) lose time while the MCU erases flash,
when interrupts are masked: measure durations with :attr:`LogLine.time`. ``dmesg`` keeps only the last 10 KB and none
of the boot; nothing of a crash report survives a reset, so keep the log read while testing something that may crash.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .._text import strip_ansi
from ..transport.base import Stream

READ_SLICE_S = 0.2


@dataclass(frozen=True)
class LogLine:
    """One line of the log: ``time`` (seconds since the epoch, this machine's clock, when the line was complete) and
    ``text`` (without ANSI colours and line end)."""

    time: float
    text: str


def read_lines(stream: Stream, seconds: float | None = None, *, clock: Callable[[], float] = time.time,
               monotonic: Callable[[], float] = time.monotonic) -> Iterator[LogLine]:
    """Lines of the log as they come, for ``seconds`` (``None``: until the caller stops iterating). A line still
    incomplete at the end is not given."""
    deadline = None if seconds is None else monotonic() + seconds
    pending = b""
    while deadline is None or monotonic() < deadline:
        slice_s = READ_SLICE_S if deadline is None else max(0.0, min(READ_SLICE_S, deadline - monotonic()))
        pending += stream.read(slice_s)
        *complete, pending = pending.split(b"\n")
        for raw in complete:
            yield LogLine(clock(), strip_ansi(raw.decode("utf-8", errors="replace")).rstrip("\r"))
