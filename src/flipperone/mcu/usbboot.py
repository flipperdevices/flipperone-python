# SPDX-License-Identifier: GPL-3.0-or-later
"""The MCU's USB bootloader (the RP2350 boot ROM) and ``picotool``, the way to write the MCU's flash over USB.

The boot ROM enumerates as ``37c1:f102`` on a Flipper One (white-labelled in the chip's OTP) and as Raspberry Pi's
``2e8a:000f`` on a new chip with an empty OTP. A chip with an empty flash starts it by itself; a running firmware
goes there with :meth:`Mcu.power_boot <flipperone.mcu.Mcu.power_boot>`. ``picotool`` must be installed (on PATH, or
pass its path); it is run with a time limit, so a lost device cannot hang the caller.

Typical use::

    mcu.power_boot()
    device = usbboot.wait_bootrom(timeout=20)
    tool = usbboot.Picotool()
    tool.load(device, Path("firmware.uf2"))
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from .._poll import wait_until
from ..errors import PortNotFound, ToolFailed, ToolNotFound
from ..transport.usb import UsbDevice, devices

log = logging.getLogger(__name__)

BOOTROM_IDS: tuple[tuple[int, int], ...] = ((0x37C1, 0xF102), (0x2E8A, 0x000F))
TIMEOUTS_S = {"erase": 400.0, "load": 180.0}    # the whole flash takes about 190 s to erase
DEFAULT_TIMEOUT_S = 30.0

Runner = Callable[..., subprocess.CompletedProcess[str]]
Finder = Callable[..., list[UsbDevice]]


def bootroms(find: Finder = devices) -> list[UsbDevice]:
    """MCUs in their USB bootloader on this host."""
    return find(BOOTROM_IDS)


def is_new_chip(device: UsbDevice) -> bool:
    """A chip whose OTP is still empty (Raspberry Pi's id, not white-labelled yet)."""
    return (device.vid, device.pid) == (0x2E8A, 0x000F)


def wait_bootrom(timeout: float, *, previous: UsbDevice | None = None, ready: Callable[[UsbDevice], bool] | None = None,
                 find: Finder = devices, sleep: Callable[[float], None] = time.sleep) -> UsbDevice:
    """The one MCU in its bootloader, once it is enumerated and ``ready`` (by default: ``picotool`` answers it; the
    OS sets its permissions a moment after it enumerates). ``previous``: a device that restarted; the old
    enumeration may still be listed for a moment, so the same bus address does not count.
    :class:`~flipperone.errors.PortNotFound` after ``timeout`` seconds, or when several are there."""
    check = ready or (lambda d: Picotool().answers(d))

    def probe() -> UsbDevice | None:
        found = bootroms(find)
        if len(found) != 1:
            return None
        d = found[0]
        if previous is not None and (d.bus, d.address) == (previous.bus, previous.address):
            return None
        return d if check(d) else None

    device = wait_until(probe, timeout, 0.5, sleep)
    if device is None:
        found = bootroms(find)
        if len(found) > 1:
            why = f"{len(found)} devices in a USB bootloader: " + "; ".join(d.describe() for d in found)
        else:
            why = "none ready"
        raise PortNotFound(f"no MCU bootloader within {timeout:g} s ({why})")
    return device


class Picotool:
    """The ``picotool`` program, pointed at one device by its USB ids."""

    def __init__(self, path: str | None = None, *, runner: Runner = subprocess.run,
                 which: Callable[[str], str | None] = shutil.which):
        self.path = path or which("picotool") or ""
        if not self.path:
            raise ToolNotFound("picotool is not installed (https://github.com/raspberrypi/picotool)")
        self._runner = runner

    def run(self, args: Sequence[str], device: UsbDevice | None = None, *, capture: bool = True,
            timeout: float | None = None) -> str:
        """Run ``picotool <args>`` (for ``device``); its stdout when ``capture``, else it prints to the terminal
        (progress bars). :class:`~flipperone.errors.ToolFailed` on an error or when it does not finish in time."""
        argv = [self.path, *args, *(_select(device) if device else [])]
        limit = timeout or TIMEOUTS_S.get(args[0], DEFAULT_TIMEOUT_S)
        log.info("$ %s", " ".join(argv))
        try:
            if capture:
                r = self._runner(argv, capture_output=True, text=True, timeout=limit)
            else:
                r = self._runner(argv, timeout=limit)
        except subprocess.TimeoutExpired:
            raise ToolFailed(f"picotool {args[0]} did not finish within {limit:g} s") from None
        out = (r.stdout or "") if capture else ""
        if r.returncode != 0:
            detail = (r.stderr or r.stdout or "").strip() if capture else ""
            raise ToolFailed(f"picotool {args[0]} failed with exit code {r.returncode}"
                             + (f": {detail}" if detail else ""))
        return out

    def answers(self, device: UsbDevice) -> bool:
        """Whether ``picotool info`` gets an answer from the device."""
        try:
            self.run(["info"], device)
        except ToolFailed:
            return False
        return True

    def info(self, device: UsbDevice) -> str:
        """``picotool info``: the program and partitions in the flash, as printed."""
        return self.run(["info"], device)

    def is_blank(self, device: UsbDevice) -> bool:
        """Nothing in the flash: no partition table, no program."""
        lines = [line.strip() for line in self.info(device).splitlines() if line.strip()]
        return lines == ["Program Information", "none"]

    def load(self, device: UsbDevice, uf2: Path, *, verify: bool = True, execute: bool = True,
             capture: bool = True) -> None:
        """Write a UF2 file into the flash, verify it and start it (``load -v -x``)."""
        args = ["load", *(["-v"] if verify else []), *(["-x"] if execute else []), str(uf2)]
        self.run(args, device, capture=capture)

    def erase_all(self, device: UsbDevice, *, capture: bool = True) -> None:
        """Erase the whole flash (about 190 s), then restart the boot ROM into itself: until then it keeps the erased
        partition table in memory. The device enumerates again: find it with ``wait_bootrom(previous=device)``."""
        self.run(["erase", "-a"], device, capture=capture)
        self.reboot(device, bootloader=True)

    def reboot(self, device: UsbDevice, *, bootloader: bool = False) -> None:
        """Restart the chip: into its firmware, or into the boot ROM again (``bootloader=True``)."""
        self.run(["reboot", *(["-u"] if bootloader else [])], device)

    def uf2_combine(self, partition_table: Path, firmware: Path, out: Path, *, partition: int = 0) -> None:
        """One UF2 of a partition table and a firmware placed into ``partition`` (``uf2 combine``). picotool tells
        file types by their extension: ``out`` must end in ``.uf2``."""
        self.run(["uf2", "combine", str(partition_table), str(firmware), str(out), "--partition", str(partition)])


def _select(device: UsbDevice) -> list[str]:
    return ["--vid", f"0x{device.vid:04x}", "--pid", f"0x{device.pid:04x}"]
