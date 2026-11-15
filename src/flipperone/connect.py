# SPDX-License-Identifier: GPL-3.0-or-later
"""Ready-made pairings of a subsystem with its usual transport. Nothing here chooses a path for you: each function
opens one specific way, and everything it does can be done by hand with :mod:`flipperone.transport`.

::

    from flipperone import connect

    with connect.mcu_over_usb() as mcu:          # the MCU's own USB port (Linux off)
        print(mcu.device_info())
    with connect.mcu_over_probe() as mcu:        # through the Debug Probe (whatever runs)
        print(mcu.uptime())
    with connect.linux_over_ssh("10.0.0.1", password="...") as linux:
        print(linux.run("uname -r").out)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import PortNotFound
from .linux import Linux
from .mcu import Mcu
from .mcu.ports import USB_SERIAL as MCU_SERIAL
from .probe import Probe
from .probe.ports import USB_SERIAL as PROBE_SERIAL
from .probe.ports import Role
from .transport.ports import wait_for
from .transport.serial import SerialStream
from .transport.ssh import SshSettings, SshShell


def serial_opener(serial: str, interface: int | None = None, *, wait_s: float = 0.0,
                  **stream_options: Any) -> Callable[[], SerialStream]:
    """A callable that finds the port by USB serial string and interface (waiting up to ``wait_s`` seconds for it
    to appear) and opens it as a :class:`~flipperone.transport.serial.SerialStream` (``stream_options`` go to it).
    The port is looked up again on every call, so the callable reopens it after a restart."""
    def open_port() -> SerialStream:
        port = wait_for(serial, interface, timeout=wait_s)
        if port is None:
            where = f"USB serial '{serial}'" + (f", interface {interface}" if interface is not None else "")
            raise PortNotFound(f"no port with {where}")
        return SerialStream(port.stable_path, **stream_options)
    return open_port


def mcu_over_usb(*, wait_s: float = 0.0, **mcu_options: Any) -> Mcu:
    """The MCU's CLI on its own USB port (present while Linux is off). ``mcu_options`` go to :class:`Mcu`."""
    return Mcu(serial_opener(MCU_SERIAL, wait_s=wait_s), **mcu_options)


def mcu_over_probe(*, wait_s: float = 0.0, **mcu_options: Any) -> Mcu:
    """The MCU's CLI through the Debug Probe (its UART; one session since the MCU started)."""
    return Mcu(serial_opener(PROBE_SERIAL, int(Role.MCU_CLI), wait_s=wait_s), **mcu_options)


def probe_cli(*, wait_s: float = 0.0, **probe_options: Any) -> Probe:
    """The Debug Probe's own CLI."""
    return Probe(serial_opener(PROBE_SERIAL, int(Role.PROBE_CLI), wait_s=wait_s), **probe_options)


def linux_over_ssh(host: str, *, user: str = "user", password: str | None = None, port: int = 22,
                   jump: str | None = None, command_timeout_s: float = 20.0) -> Linux:
    """Linux on the device over SSH (needs ``flipperone[ssh]``); connects on the first command."""
    shell = SshShell(SshSettings(host=host, user=user, password=password, port=port, jump=jump))
    return Linux(shell, command_timeout_s=command_timeout_s)
