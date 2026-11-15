# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the MCU's CLI is on the host's USB.

The MCU's own USB CDC port (VID 0x37C1, PID 0xF101, USB serial string ``flip_one_mcu``) is on the device's USB-C1
while Linux is off; once Linux runs, USB-C1 belongs to the main board. macOS names it
``/dev/cu.usbmodemflip_one_mcu1``, Linux ``/dev/ttyACM<n>`` behind ``/dev/serial/by-id/..._flip_one_mcu-if00``.
The same CLI is reachable through the Debug Probe (:mod:`flipperone.probe`) whatever runs.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..transport.ports import Port, discover, find, wait_for

USB_VID = 0x37C1
USB_PID = 0xF101
USB_SERIAL = "flip_one_mcu"


def usb_port(ports: Sequence[Port] | None = None) -> Port | None:
    """The MCU's own USB port, when it is enumerated."""
    return find(discover() if ports is None else ports, USB_SERIAL)


def wait_usb_port(timeout: float | None = None) -> Port | None:
    """Wait for the MCU's own USB port; ``None`` after ``timeout`` seconds (``None`` waits forever)."""
    return wait_for(USB_SERIAL, timeout=timeout)
