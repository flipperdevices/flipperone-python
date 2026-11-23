# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental: the CPU (Linux) powered on and off by the MCU, watched on the CPU's serial console. Needs the MCU's
CLI (:class:`~flipperone.mcu.Mcu`) and the console (:class:`~flipperone.transport.console.SerialShell`), both through
the Debug Probe. Behaviour as flipperone-mcu-firmware's agent tools found it (scripts/agent_tools, 2026-11).

How the device does it:

- the MCU powers the CPU while its app :data:`~flipperone.mcu.HOST_APP` runs; stopping the app cuts the power
  (Linux gets no warning). Linux does not start by itself after the MCU starts, after a shutdown, or after a
  ``reboot`` inside Linux (it then waits in the boot menu);
- how it boots depends on the image. Development images: U-Boot scans for some seconds, prints ``(N bootflows, N
  valid)`` with the entries (``/loader/entries/*.conf``) in menu order on the console, then waits in its menu, also on
  the device's screen, for the arrow keys and Enter. Release images (bundle 0.1.0, image 1371): no such menu, the
  boot menu picks the default profile by itself (``Booting Desktop`` on the console about 10 s after power-on) and
  the console logs ``user`` in some seconds later;
- the CPU's power rails are held by an I/O expander that keeps its outputs: a reset of the MCU alone leaves Linux
  running, and the MCU's app then attaches to it without a restart. Rarely the MCU fails to set the expander up at
  such a boot (its bus is shared with the running CPU: ``Failed to initialize Main Expander``); it then cannot control
  the CPU's power until its next reset;
- systemd ignores a ``poweroff`` issued while it is still starting up, some tens of seconds after the shell first
  answers; a Ctrl-C on the console interrupts a pending one;
- keys typed on the console while it boots are taken by the boot: a Ctrl-C or Enter (what
  :meth:`~flipperone.transport.console.SerialShell.ready`, :func:`state` and every console command send first) stops
  a release image's boot menu in a root shell of its initramfs (``~ #``, host name ``buildroot``, no ``sudo``), and
  picks an entry in U-Boot's menu. :func:`start` only listens until the user's prompt appears; leave the console
  alone meanwhile.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from .._text import strip_ansi
from ..errors import FlipperOneError
from ..mcu import HOST_APP, MASKROM_APP, Mcu
from ..transport.base import Stream
from ..transport.console import SerialShell

DOWN = b"\x1b[B"
ENTRY = re.compile(r"/loader/entries/(?:\d+-)?(?:flipperos-)?(\S+)\.conf")
BOOTING = re.compile(r"Booting (?!Linux )(\S+)\r?\n")    # a release image's boot menu choosing by itself; not the
                                                        # kernel's "Booting Linux on physical CPU"
MENU_OR_BOOT = re.compile(rb"bootflows,|Booting (?!Linux )\S+\r?\n")
USER_PROMPT = re.compile(rb"\w+@[\w.-]+:\S*\$ ")        # the logged-in user's shell (user@flipperone-189a05:~$)
UPTIME = re.compile(r"^\d+\.\d+$", re.M)
READ_SLICE_S = 0.1


class HostError(FlipperOneError):
    """The CPU could not be brought to the state asked for; the message says where it stands."""


class HostState(StrEnum):
    OFF = "off"
    BOOTING = "powered_no_shell"                     # booting, in the boot menu, at U-Boot's or a login prompt
    UP = "up"
    UP_NO_HOST_APP = "up_no_host_app"                # the MCU was reset while Linux ran; screen and keys are the MCU's
    POWERED_NO_HOST_APP = "powered_no_shell_no_host_app"
    MASKROM = "maskrom"                              # the CPU in its boot ROM, waiting for a loader over USB


@dataclass(frozen=True)
class Started:
    """What :func:`start` did: the boot entries U-Boot listed and the one chosen (from 1); or, on an image that
    boots by itself, what it booted (``booted``: ``Desktop``; no entries then); or that it attached to a Linux that
    was already up (``attached``)."""

    entries: list[str]
    entry: int | None
    attached: bool = False
    booted: str | None = None


def state(mcu: Mcu, console: SerialShell) -> HostState:
    """Where the CPU stands, from the MCU's running app and the console: about a second, no screenshot."""
    app = mcu.desktop_run_app()
    if app == MASKROM_APP:
        return HostState.MASKROM
    ready, printed = console.ready()
    if app == HOST_APP:
        return HostState.UP if ready else HostState.BOOTING
    if ready:
        return HostState.UP_NO_HOST_APP
    return HostState.POWERED_NO_HOST_APP if printed else HostState.OFF


def boot_entries(scan: str) -> list[str]:
    """Entry names from U-Boot's scan output, in menu order."""
    return ENTRY.findall(scan)


def entry_position(wanted: int | str, entries: list[str]) -> int:
    """Menu position (from 1) of ``wanted``: a number, or text exactly one entry name contains (any case)."""
    if isinstance(wanted, int) or wanted.isdigit():
        position = int(wanted)
        if position < 1 or (entries and position > len(entries)):
            raise HostError(f"there is no boot entry {position}; U-Boot listed {len(entries)}: {entries}")
        return position
    matching = [n for n, name in enumerate(entries, 1) if wanted.lower() in name.lower()]
    if len(matching) != 1:
        raise HostError(f"{wanted!r} matches {len(matching)} boot entries, it has to match one: {entries}")
    return matching[0]


def uptime_s(output: str) -> float:
    """Seconds from ``cut -d' ' -f1 /proc/uptime`` (kernel messages may be mixed in)."""
    numbers = UPTIME.findall(output)
    if not numbers:
        raise HostError(f"no uptime in {output[-200:]!r}")
    return float(numbers[-1])


def start(mcu: Mcu, console: SerialShell, entry: int | str | None = None, *, wait_s: float = 120.0,
          sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> Started:
    """Power the CPU and wait up to ``wait_s`` for the shell (0: not at all). Where U-Boot shows its menu, choose
    ``entry`` (a number or part of a name; ``None``: the first); an image that boots by itself takes its default,
    and asking for an ``entry`` there fails once it is up. A Linux already up without the MCU's app (the MCU was
    reset) is attached to instead, checked by its uptime going on. Fails, with the CPU off again where it can be,
    when another MCU app runs, the entry is not there, U-Boot says ``Boot failed`` (then at its prompt: :func:`stop`
    with ``hard``) or the CPU stays silent."""
    app = mcu.desktop_run_app()
    if app == HOST_APP:
        raise HostError("the CPU is powered already (the MCU's host app runs)")
    if app is not None:
        raise HostError(f"the MCU runs app {app!r}: close it first (desktop stop_app, or the Back key)")
    if console.ready()[0]:
        return _attach(mcu, console, sleep)
    stream = console.stream
    stream.reset_input()
    mcu.desktop_start_app(HOST_APP)
    _read_quiet(stream, 1.0, 0.5, clock)                      # the probe's banner
    if not _read_quiet(stream, 8.0, 0.2, clock):
        # the app powers only a CPU whose rails read off: one that powered itself down meanwhile is cut and started
        mcu.desktop_stop_app()
        sleep(1.5)
        mcu.desktop_start_app(HOST_APP)
    seen = _read_until(stream, MENU_OR_BOOT, 40.0, clock)      # the raw output since power-on, kept for the prompt
    scan = _clean(seen)
    by_itself = BOOTING.search(scan) if "bootflows," not in scan else None
    if by_itself is None and "bootflows," not in scan:
        if not scan.strip():
            mcu.desktop_stop_app()
            raise HostError("the CPU shows no sign of life after power-on: the MCU may have lost control of its "
                            "power (reset the MCU with the CPU off, then start again)")
        raise HostError(f"no boot menu and no boot in 40 s; the console printed: {scan.strip()[-400:]}")
    if by_itself is not None:
        result, what = Started([], None, booted=by_itself.group(1)), f"booting {by_itself.group(1)}"
    else:
        entries = boot_entries(scan)
        try:
            position = entry_position(1 if entry is None else entry, entries)
        except HostError:
            mcu.desktop_stop_app()
            raise
        sleep(1.0)
        stream.write(DOWN * (position - 1) + b"\r")
        after = _read_quiet(stream, 8.0, 1.5, clock)
        seen += after
        booting = _clean(after)
        if "Boot failed" in booting:
            raise HostError(f"U-Boot could not boot entry {position}; it is at its prompt: {booting.strip()[-300:]}")
        result, what = Started(entries, position), f"choosing entry {position}"
    if wait_s > 0 and USER_PROMPT.search(seen) is None and \
            USER_PROMPT.search(_read_until(stream, USER_PROMPT, wait_s, clock)) is None:
        raise HostError(f"no user's shell prompt on the console {wait_s:g} s after {what}")
    if by_itself is not None and entry is not None:
        raise HostError(f"this image has no boot menu to choose {entry!r} from: it booted {result.booted} by itself "
                        "and is up")
    return result


def stop(mcu: Mcu, console: SerialShell, *, hard: bool = False, timeout_s: float = 90.0,
         sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> bool:
    """Power the CPU off: ``sync`` and ``poweroff`` in Linux, waiting for the kernel's ``Power down`` (sent again
    while systemd still starts up), or with ``hard`` a ``sync`` where the shell answers and the MCU cutting the
    power. Returns False when it was off already. Then waits until the MCU's app has ended."""
    app = mcu.desktop_run_app()
    ready, _ = console.ready()
    if app != HOST_APP and not ready:
        return False
    if hard:
        if ready:
            console.run("sync", 20.0)
        if app != HOST_APP:
            mcu.desktop_start_app(HOST_APP)       # the app cuts the power on its way out, so it has to run
            sleep(1.0)
        mcu.desktop_stop_app()
    else:
        if not ready:
            raise HostError("the console shows no shell prompt: a clean shutdown is not possible (hard=True)")
        _poweroff(console, timeout_s, clock)
    deadline = clock() + 20.0
    while mcu.desktop_run_app() == HOST_APP:
        if clock() >= deadline:
            raise HostError("the CPU is down but the MCU's host app still runs")
        sleep(1.0)
    return True


def _attach(mcu: Mcu, console: SerialShell, sleep: Callable[[float], None]) -> Started:
    if "Main Expander" in mcu.dmesg():
        raise HostError("Linux is up, but this MCU boot could not set up the main expander, so it cannot control the "
                        "CPU's power: reset the MCU again, then start")
    before = uptime_s(console.run("sync; cut -d' ' -f1 /proc/uptime", 20.0).out)
    mcu.desktop_start_app(HOST_APP)
    sleep(3.0)
    try:
        after = uptime_s(console.run("cut -d' ' -f1 /proc/uptime", 10.0).out)
    except FlipperOneError:
        after = 0.0
    if after <= before:
        raise HostError("the MCU power-cycled the CPU instead of attaching to it (a sync was done first); it is "
                        "restarting")
    return Started([], None, attached=True)


def _poweroff(console: SerialShell, timeout_s: float, clock: Callable[[], float]) -> None:
    """Nothing is typed while waiting: a Ctrl-C would interrupt the poweroff."""
    stream = console.stream
    deadline = clock() + timeout_s
    under_way = False
    while True:
        if not under_way:
            stream.write(b"sync; sudo -n poweroff\r")
        seen = _read_until(stream, b"Power down", min(30.0, max(deadline - clock(), 1.0)), clock)
        if b"Power down" in seen:
            return
        if clock() >= deadline:
            raise HostError(f"Linux did not power down in {timeout_s:g} s; the console printed: "
                            f"{_clean(seen)[-300:]}")
        under_way = under_way or b"power off now" in seen


def _read_until(stream: Stream, marker: bytes | re.Pattern[bytes], timeout: float,
                clock: Callable[[], float]) -> bytes:
    """What arrives until ``marker`` (bytes, or a pattern) is in it, or ``timeout`` passes (then all that came)."""
    def seen(buf: bytearray) -> bool:
        return marker in buf if isinstance(marker, bytes) else marker.search(buf) is not None
    deadline = clock() + timeout
    buf = bytearray()
    while not seen(buf) and (remaining := deadline - clock()) > 0:
        buf += stream.read(min(remaining, READ_SLICE_S))
    return bytes(buf)


def _read_quiet(stream: Stream, timeout: float, quiet: float, clock: Callable[[], float]) -> bytes:
    """What arrives until ``quiet`` seconds pass without a byte, ``timeout`` at most."""
    deadline = clock() + timeout
    buf = bytearray()
    last = clock()
    while (now := clock()) < deadline and now - last < quiet:
        data = stream.read(min(deadline - now, READ_SLICE_S))
        if data:
            buf += data
            last = clock()
    return bytes(buf)


def _clean(data: bytes) -> str:
    return strip_ansi(data.decode("utf-8", errors="replace")).replace("\r", "")
