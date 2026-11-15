# SPDX-License-Identifier: GPL-3.0-or-later
"""The CPU (Rockchip RK3576) in MaskROM or loader mode on USB, through ``rockusb`` (collabora/rockchiprs).

In MaskROM the boot ROM answers only code-download requests: chip information and storage commands need a loader
first (:meth:`Rockusb.download_boot`). The mode is told from the USB descriptor (``bcdUSB`` 0x0200 is the boot ROM,
0x0201 a running loader), read from the OS. ``rockusb`` must be installed (on PATH, or pass its path).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ._poll import wait_until
from .errors import FlipperOneError, ToolFailed, ToolNotFound
from .transport.usb import usb_bcd

log = logging.getLogger(__name__)

ROCKCHIP_VID = 0x2207
SOC_BY_PID = {0x350E: "RK3576", 0x350B: "RK3588", 0x350A: "RK3568", 0x330C: "RK3399"}
_LIST_LINE = re.compile(r"^\*\s*Bus\s+(\d+)\s+Device\s+(\d+)\s+ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})")

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class MaskromError(FlipperOneError):
    """The device is not in the mode an operation needs."""


def mode_from_bcd(bcd: int) -> str:
    """``"maskrom"`` for bcdUSB 0x0200 (the boot ROM), ``"loader"`` for the odd 0x0201 (rkdeveloptool's rule)."""
    return "loader" if bcd & 1 else "maskrom"


@dataclass(frozen=True)
class Device:
    """A Rockchip device on USB, as ``rockusb list`` shows it."""

    bus: int
    address: int
    vid: int
    pid: int

    @property
    def soc(self) -> str:
        return SOC_BY_PID.get(self.pid, "unknown")

    @property
    def selector(self) -> str:
        """``bus:address``, the form ``rockusb -d`` takes."""
        return f"{self.bus}:{self.address}"


def parse_list(output: str) -> list[Device]:
    """Devices from ``rockusb list`` lines such as ``* Bus 2 Device 5 ID 2207:350e``."""
    found = []
    for line in output.splitlines():
        m = _LIST_LINE.match(line.strip())
        if m:
            found.append(Device(int(m[1]), int(m[2]), int(m[3], 16), int(m[4], 16)))
    return found


def _run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), capture_output=True, text=True)


class Rockusb:
    """The ``rockusb`` program."""

    def __init__(self, path: str | None = None, *, runner: Runner = _run,
                 usb_bcd_fn: Callable[[int, int], int | None] = usb_bcd,
                 which: Callable[[str], str | None] = shutil.which):
        self.path = path or which("rockusb") or ""
        if not self.path:
            raise ToolNotFound("rockusb is not installed (https://github.com/collabora/rockchiprs)")
        self._runner = runner
        self._usb_bcd = usb_bcd_fn

    def run(self, *args: str, device: Device | None = None) -> subprocess.CompletedProcess[str]:
        """``rockusb [-d bus:address] <args>`` as it finished (the caller judges the exit code)."""
        argv = [self.path, *(["-d", device.selector] if device else []), *args]
        log.info("$ %s", " ".join(argv))
        return self._runner(argv)

    def list(self) -> list[Device]:
        """Rockchip devices in MaskROM or loader mode."""
        r = self.run("list")
        if r.returncode != 0:
            raise ToolFailed(f"rockusb list failed: {(r.stderr or r.stdout).strip()}")
        return [d for d in parse_list(r.stdout) if d.vid == ROCKCHIP_VID]

    def wait(self, timeout: float | None = None, poll: float = 1.0, sleep: Callable[[float], None] = time.sleep,
             clock: Callable[[], float] = time.monotonic) -> Device | None:
        """The first device to appear; ``None`` after ``timeout`` seconds (``None`` waits forever)."""
        found = wait_until(lambda: self.list() or None, timeout, poll, sleep, clock)
        return found[0] if found else None

    def mode(self, device: Device) -> str | None:
        """``"maskrom"`` or ``"loader"``, from the USB descriptor; ``None`` when the OS does not tell."""
        bcd = self._usb_bcd(device.bus, device.address)
        return None if bcd is None else mode_from_bcd(bcd)

    def download_boot(self, device: Device, loader: Path) -> str:
        """Send a loader into a device in MaskROM (``download-boot``); its output. Refused in loader mode: a loader
        runs there already."""
        if self.mode(device) == "loader":
            raise MaskromError(f"{device.selector} runs a loader already: power-cycle it into MaskROM first")
        r = self.run("download-boot", str(loader), device=device)
        out = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            raise ToolFailed(f"rockusb download-boot failed with exit code {r.returncode}: {out}")
        return out
