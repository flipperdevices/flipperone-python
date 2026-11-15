# SPDX-License-Identifier: GPL-3.0-or-later
"""USB device descriptors from the operating system, for devices identified by bus and address.

Some state is only visible in descriptors, not through the device's own protocol: a Rockchip SoC in
MaskROM mode reports ``bcdUSB`` 0x0200 and answers nothing but the code-download requests, while a
running loader reports 0x0201. macOS: ``ioreg`` (plist output); Linux: sysfs.
"""

from __future__ import annotations

import plistlib
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SYSFS_USB = Path("/sys/bus/usb/devices")


def usb_bcd(bus: int, address: int, platform: str = sys.platform) -> int | None:
    """``bcdUSB`` of the device (e.g. ``0x0200``), or ``None`` when it cannot be read on this platform."""
    if platform == "darwin":
        return _bcd_ioreg(bus, address)
    if platform.startswith("linux"):
        return _bcd_sysfs(bus, address)
    return None


def bcd_text(bcd: int) -> str:
    """``0x0201`` -> ``"2.01"``, the form sysfs and lsusb print."""
    return f"{bcd >> 8:x}.{bcd & 0xFF:02x}"


def bcd_from_text(text: str) -> int:
    """``"2.01"`` -> ``0x0201``."""
    major, minor = text.strip().split(".")
    return (int(major, 16) << 8) | int(minor, 16)


def _bcd_ioreg(bus: int, address: int,
               run: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run) -> int | None:
    r = run(["ioreg", "-p", "IOUSB", "-l", "-w0", "-a"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return bcd_from_ioreg_plist(plistlib.loads(r.stdout), bus, address)


def bcd_from_ioreg_plist(root: Any, bus: int, address: int) -> int | None:
    """Walk the registry: the bus is the top byte of ``locationID`` (as nusb reports it), the address is
    ``USB Address``."""
    stack: list[Any] = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            location, addr, bcd = node.get("locationID"), node.get("USB Address"), node.get("bcdUSB")
            if isinstance(location, int) and (location >> 24) == bus and addr == address and isinstance(bcd, int):
                return bcd
            stack.extend(node.get("IORegistryEntryChildren", []))
    return None


def _bcd_sysfs(bus: int, address: int, sysfs: Path = SYSFS_USB) -> int | None:
    if not sysfs.is_dir():
        return None
    for dev in sysfs.iterdir():
        try:
            if int((dev / "busnum").read_text()) == bus and int((dev / "devnum").read_text()) == address:
                return bcd_from_text((dev / "version").read_text())
        except (OSError, ValueError):
            continue
    return None


@dataclass(frozen=True)
class UsbDevice:
    vid: int
    pid: int
    bus: int
    address: int
    serial: str | None = None

    @property
    def id(self) -> str:
        return f"{self.vid:04x}:{self.pid:04x}"

    def describe(self) -> str:
        serial = f", serial {self.serial}" if self.serial else ""
        return f"{self.id} at bus {self.bus} address {self.address}{serial}"


def devices(ids: Iterable[tuple[int, int]], platform: str = sys.platform,
            run: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
            sysfs: Path = SYSFS_USB) -> list[UsbDevice]:
    """The USB devices whose (vendor, product) is one of ``ids``. Linux: sysfs; macOS: ``ioreg``; empty elsewhere."""
    wanted = set(ids)
    if platform.startswith("linux"):
        found = _devices_sysfs(sysfs)
    elif platform == "darwin":
        r = run(["ioreg", "-p", "IOUSB", "-l", "-w0", "-a"], capture_output=True)
        found = devices_from_ioreg_plist(plistlib.loads(r.stdout)) if r.returncode == 0 and r.stdout else []
    else:
        found = []
    return sorted((d for d in found if (d.vid, d.pid) in wanted), key=lambda d: (d.bus, d.address))


def _devices_sysfs(sysfs: Path) -> list[UsbDevice]:
    found: list[UsbDevice] = []
    if not sysfs.is_dir():
        return found
    for dev in sysfs.iterdir():
        try:
            vid, pid = int((dev / "idVendor").read_text(), 16), int((dev / "idProduct").read_text(), 16)
            bus, address = int((dev / "busnum").read_text()), int((dev / "devnum").read_text())
        except (OSError, ValueError):
            continue        # interfaces and hubs' ports have no descriptor files
        serial = (dev / "serial").read_text().strip() if (dev / "serial").is_file() else None
        found.append(UsbDevice(vid, pid, bus, address, serial))
    return found


def devices_from_ioreg_plist(root: Any) -> list[UsbDevice]:
    found: list[UsbDevice] = []
    stack: list[Any] = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            vid, pid, location, addr = (node.get(k) for k in ("idVendor", "idProduct", "locationID", "USB Address"))
            if isinstance(vid, int) and isinstance(pid, int) and isinstance(location, int) and isinstance(addr, int):
                found.append(UsbDevice(vid, pid, location >> 24, addr, node.get("USB Serial Number")))
            stack.extend(node.get("IORegistryEntryChildren", []))
    return found
