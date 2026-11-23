# SPDX-License-Identifier: GPL-3.0-or-later
"""Finding USB serial ports by USB serial string and interface number.

A port is identified by its USB serial string plus USB interface number (the Flipper One's MCU: ``flip_one_mcu``;
the Debug Probe: ``f1_debug_xxxx_``, one per probe, with interfaces 2, 4, 6, 8); that pair is stable across hosts and
re-plugs. Where a serial string differs per device, a compiled regular expression stands for it. Each CDC ACM
port is two USB interfaces, the communication one and the data one right after it (the Debug Probe: 1+2, 3+4, 5+6,
7+8; the MCU's own port: 0+1), and the two systems name a port by different halves. macOS appends the data
interface to the device name (``cu.usbmodemf1_debug_4b30_4`` -> 4); Linux binds the tty to the communication
interface and shows that one, in pyserial's ``location`` (``3-1:1.3``) and in ``/dev/serial/by-id`` names
(``...-if03-port0``). The number used here is the data interface: Linux's number plus one.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from serial.tools import list_ports

from .._poll import wait_until

BY_ID_DIR = Path("/dev/serial/by-id")

_TRAILING_DIGITS = re.compile(r"(\d+)$")
_LOCATION_INTERFACE = re.compile(r":\d+\.(\d+)$")
_BY_ID_INTERFACE = re.compile(r"-if(\d+)(?:-port\d+)?$")

Serial = str | re.Pattern[str]    # a USB serial string, or a pattern for one that differs per device


@dataclass(frozen=True)
class Port:
    device: str            # OS device node: /dev/cu.usbmodemf1_debug_4b30_4, /dev/ttyACM1
    stable_path: str       # survives re-plugging: /dev/serial/by-id symlink on Linux, else device
    serial: str | None
    interface: int | None
    vid: int | None
    pid: int | None
    product: str | None

    def matches(self, serial: Serial, interface: int | None) -> bool:
        """``serial``: the exact string, or a pattern the whole string must match."""
        if isinstance(serial, str):
            same = self.serial == serial
        else:
            same = self.serial is not None and serial.fullmatch(self.serial) is not None
        return same and (interface is None or self.interface == interface)


def interface_from_mac_name(name: str, serial: str | None) -> int | None:
    """``cu.usbmodemf1_debug_4b30_4`` with serial ``f1_debug_4b30_`` -> 4."""
    if serial and serial in name:
        tail = name.split(serial, 1)[1]
        return int(tail) if tail.isdigit() else None
    m = _TRAILING_DIGITS.search(name)
    return int(m.group(1)) if m else None


def interface_from_location(location: str | None) -> int | None:
    """Linux pyserial location ``1-2.3:1.3`` -> 3 (configuration 1, interface 3: the communication one)."""
    m = _LOCATION_INTERFACE.search(location or "")
    return int(m.group(1)) if m else None


def interface_from_by_id(path: str) -> int | None:
    """``/dev/serial/by-id/usb-..._f1_debug_4b30_-if03`` -> 3 (the communication interface)."""
    m = _BY_ID_INTERFACE.search(path)
    return int(m.group(1)) if m else None


def by_id_links(directory: Path = BY_ID_DIR) -> dict[str, str]:
    """Map resolved device path -> ``/dev/serial/by-id`` symlink. Empty where the directory does not exist."""
    if not directory.is_dir():
        return {}
    return {str(link.resolve()): str(link) for link in directory.iterdir() if link.is_symlink()}


def discover(ports: Iterable[Any] | None = None, by_id: Mapping[str, str] | None = None,
             platform: str = sys.platform) -> list[Port]:
    """USB serial ports that carry a serial string, sorted by (serial, interface).

    ``ports`` (pyserial ``ListPortInfo``-like objects) and ``by_id`` are injectable for tests.
    """
    if ports is None:
        ports = list_ports.comports()
    if by_id is None:
        by_id = by_id_links() if platform.startswith("linux") else {}
    found: list[Port] = []
    for p in ports:
        serial = p.serial_number or None
        if serial is None:
            continue
        device = p.device
        if platform == "darwin":
            stable = device
            interface = interface_from_mac_name(p.name or Path(device).name, serial)
        else:
            stable = by_id.get(str(Path(device).resolve()), by_id.get(device, device))
            interface = interface_from_location(p.location)
            if interface is None:
                interface = interface_from_by_id(stable)
            if interface is not None:
                interface += 1      # the communication interface -> its data interface, as macOS numbers it
        found.append(Port(device=device, stable_path=stable, serial=serial, interface=interface,
                          vid=p.vid, pid=p.pid, product=p.product))
    return sorted(found, key=lambda x: (x.serial or "", -1 if x.interface is None else x.interface, x.device))


def find(ports: Iterable[Port], serial: Serial, interface: int | None = None) -> Port | None:
    """First port with this serial string, or one matching the pattern (and interface number, if given)."""
    return next((p for p in ports if p.matches(serial, interface)), None)


def wait_for(serial: Serial, interface: int | None = None, timeout: float | None = None, poll: float = 0.5,
             discover_fn: Callable[[], list[Port]] = discover, sleep: Callable[[float], None] = time.sleep,
             clock: Callable[[], float] = time.monotonic) -> Port | None:
    """Poll until the port is present. ``timeout`` in seconds, ``None`` waits forever; returns ``None`` on timeout."""
    return wait_until(lambda: find(discover_fn(), serial, interface), timeout, poll, sleep, clock)
