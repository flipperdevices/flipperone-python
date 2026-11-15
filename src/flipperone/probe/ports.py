# SPDX-License-Identifier: GPL-3.0-or-later
"""The Flipper One Debug Probe's serial ports (VID 0x37C1, PID 0xF131, USB serial string ``flip_one_debug``).

Four CDC ports, numbered by their USB data interface: the CPU's console (2), the MCU's CLI (4), the MCU's log (6) and
the probe's own CLI (8). All run at 1500000 baud. macOS names them ``/dev/cu.usbmodemflip_one_debug<n>``; Linux
``/dev/ttyACM*`` behind ``/dev/serial/by-id/..._flip_one_debug-if0<n-1>``.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import IntEnum

from ..transport.ports import Port, discover, find, wait_for

USB_VID = 0x37C1
USB_PID = 0xF131
USB_SERIAL = "flip_one_debug"


class Role(IntEnum):
    """What a probe port carries, valued by its USB interface number."""

    CPU_CONSOLE = 2
    MCU_CLI = 4
    MCU_LOG = 6
    PROBE_CLI = 8


def port(role: Role, ports: Sequence[Port] | None = None) -> Port | None:
    """The probe's port for ``role``, when the probe is connected."""
    return find(discover() if ports is None else ports, USB_SERIAL, int(role))


def wait_port(role: Role, timeout: float | None = None) -> Port | None:
    """Wait for the probe's port for ``role``; ``None`` after ``timeout`` seconds (``None`` waits forever)."""
    return wait_for(USB_SERIAL, int(role), timeout=timeout)
