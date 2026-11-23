# SPDX-License-Identifier: GPL-3.0-or-later
"""The Flipper One Debug Probe's serial ports (VID 0x37C1, PID 0xF131), firmware 0.7.0 and newer.

Each probe has its own USB serial string, ``f1_debug_xxxx_``: four hex digits folded from its chip ID, whose full
value ends the USB product string (``Flipper One Debug Probe D7DA0C50B04820F2``). Four CDC ports, numbered by their
USB data interface: the CPU's console (2), the MCU's CLI (4), the MCU's log (6) and the probe's own CLI (8). All run at
1500000 baud whatever the host asks for. macOS names them ``/dev/cu.usbmodemf1_debug_xxxx_<n>``; Linux
``/dev/ttyACM*`` behind ``/dev/serial/by-id/..._f1_debug_xxxx_-if0<n-1>``. A probe with older firmware has the serial
``flip_one_debug`` and is not found here: update it (https://github.com/flipperdevices/flipperone-debug-probe).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum

from .._poll import wait_until
from ..errors import AmbiguousDevice
from ..transport.ports import Port, discover, find

USB_VID = 0x37C1
USB_PID = 0xF131
USB_SERIAL = re.compile(r"f1_debug_[0-9a-f]{4}_")


class Role(IntEnum):
    """What a probe port carries, valued by its USB interface number."""

    CPU_CONSOLE = 2
    MCU_CLI = 4
    MCU_LOG = 6
    PROBE_CLI = 8


@dataclass(frozen=True)
class ProbeId:
    """One attached probe: its USB serial string and its chip ID (from the product string; ``None`` if absent)."""

    serial: str
    chip_id: str | None

    def is_named(self, name: str) -> bool:
        """Whether ``name`` picks this probe: the four hex digits of its serial, the whole serial, or its chip ID or
        the beginning of it (any case)."""
        name = name.lower()
        return (self.serial in (name, f"f1_debug_{name}_")
                or (self.chip_id is not None and len(name) >= 4 and self.chip_id.lower().startswith(name)))


def probes(ports: Sequence[Port] | None = None) -> list[ProbeId]:
    """The attached probes, by serial."""
    found: dict[str, ProbeId] = {}
    for p in discover() if ports is None else ports:
        if p.serial is not None and USB_SERIAL.fullmatch(p.serial):
            tail = (p.product or "").split()[-1:] or [""]
            chip = tail[0].upper() if re.fullmatch(r"[0-9A-Fa-f]{16}", tail[0]) else None
            found.setdefault(p.serial, ProbeId(p.serial, chip))
    return [found[s] for s in sorted(found)]


def select(attached: Sequence[ProbeId], probe: str | None = None) -> ProbeId | None:
    """The probe to use: the one ``probe`` names (:meth:`ProbeId.is_named`), or the only one attached; ``None`` when
    none is (or none of that name). Several attached and none named: :class:`~flipperone.errors.AmbiguousDevice`."""
    if probe is not None:
        named = [p for p in attached if p.is_named(probe)]
        if len(named) > 1:
            raise AmbiguousDevice(f"probe {probe!r} matches several probes: {_listed(named)}")
        return named[0] if named else None
    if len(attached) > 1:
        raise AmbiguousDevice(f"several Debug Probes are attached: {_listed(attached)}; name one (its serial's four "
                              "hex digits or its chip ID)")
    return attached[0] if attached else None


def port(role: Role, ports: Sequence[Port] | None = None, probe: str | None = None) -> Port | None:
    """The port for ``role`` of the probe :func:`select` picks, when it is connected."""
    ports = discover() if ports is None else ports
    chosen = select(probes(ports), probe)
    return find(ports, chosen.serial, int(role)) if chosen is not None else None


def wait_port(role: Role, timeout: float | None = None, probe: str | None = None,
              discover_fn: Callable[[], list[Port]] = discover) -> Port | None:
    """Wait for the port for ``role``; ``None`` after ``timeout`` seconds (``None`` waits forever)."""
    return wait_until(lambda: port(role, discover_fn(), probe), timeout, poll=0.5)


def _listed(attached: Sequence[ProbeId]) -> str:
    return ", ".join(f"{p.serial} ({p.chip_id or 'no chip ID'})" for p in attached)
