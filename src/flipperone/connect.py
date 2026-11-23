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
    with connect.linux_over_probe() as linux:    # the CPU's serial console: no network needed
        print(linux.run("uname -r").out)

With several Debug Probes attached, ``probe=`` names one: the four hex digits of its serial or its chip ID
(:func:`flipperone.probe.select`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import PortNotFound
from .linux import Linux
from .mcu import Mcu
from .mcu.ports import USB_SERIAL as MCU_SERIAL
from .probe import Probe
from .probe.ports import Role, wait_port
from .transport.console import SerialShell
from .transport.ports import Serial, wait_for
from .transport.serial import SerialStream
from .transport.ssh import SshSettings, SshShell


def serial_opener(serial: Serial, interface: int | None = None, *, wait_s: float = 0.0,
                  **stream_options: Any) -> Callable[[], SerialStream]:
    """A callable that finds the port by USB serial string and interface (waiting up to ``wait_s`` seconds for it
    to appear) and opens it as a :class:`~flipperone.transport.serial.SerialStream` (``stream_options`` go to it).
    The port is looked up again on every call, so the callable reopens it after a restart."""
    def open_port() -> SerialStream:
        port = wait_for(serial, interface, timeout=wait_s)
        if port is None:
            shown = serial if isinstance(serial, str) else serial.pattern
            where = f"USB serial '{shown}'" + (f", interface {interface}" if interface is not None else "")
            raise PortNotFound(f"no port with {where}")
        return SerialStream(port.stable_path, **stream_options)
    return open_port


def mcu_over_usb(*, wait_s: float = 0.0, **mcu_options: Any) -> Mcu:
    """The MCU's CLI on its own USB port (present while Linux is off). ``mcu_options`` go to :class:`Mcu`."""
    return Mcu(serial_opener(MCU_SERIAL, wait_s=wait_s), **mcu_options)


def probe_opener(role: Role, *, probe: str | None = None, wait_s: float = 0.0,
                 **stream_options: Any) -> Callable[[], SerialStream]:
    """Like :func:`serial_opener`, for a Debug Probe port: the probe is chosen (``probe``) on every call."""
    def open_port() -> SerialStream:
        port = wait_port(role, timeout=wait_s, probe=probe)
        if port is None:
            named = f" {probe!r}" if probe is not None else ""
            raise PortNotFound(f"no Debug Probe{named} with its {role.name} port (firmware 0.7.0 or newer)")
        return SerialStream(port.stable_path, **stream_options)
    return open_port


def mcu_over_probe(*, probe: str | None = None, wait_s: float = 0.0, **mcu_options: Any) -> Mcu:
    """The MCU's CLI through the Debug Probe (its UART; one session since the MCU started)."""
    return Mcu(probe_opener(Role.MCU_CLI, probe=probe, wait_s=wait_s), **mcu_options)


def probe_cli(*, probe: str | None = None, wait_s: float = 0.0, **probe_options: Any) -> Probe:
    """The Debug Probe's own CLI."""
    return Probe(probe_opener(Role.PROBE_CLI, probe=probe, wait_s=wait_s), **probe_options)


def mcu_log_over_probe(*, probe: str | None = None, wait_s: float = 0.0) -> SerialStream:
    """The MCU's log port of the Debug Probe, open; read it with :func:`flipperone.mcu.log.read_lines`."""
    return probe_opener(Role.MCU_LOG, probe=probe, wait_s=wait_s)()


def cpu_console_over_probe(*, probe: str | None = None, wait_s: float = 0.0) -> SerialShell:
    """The CPU's serial console the Debug Probe bridges, as a shell (see :mod:`flipperone.transport.console` for
    what a console cannot do); :mod:`flipperone.experimental.host` watches the CPU's power on it."""
    return SerialShell(probe_opener(Role.CPU_CONSOLE, probe=probe, wait_s=wait_s)())


def linux_over_probe(*, probe: str | None = None, wait_s: float = 0.0, command_timeout_s: float = 30.0) -> Linux:
    """Linux on the device over the CPU's serial console (:func:`cpu_console_over_probe`): no network needed."""
    return Linux(cpu_console_over_probe(probe=probe, wait_s=wait_s), command_timeout_s=command_timeout_s)


def linux_over_ssh(host: str, *, user: str = "user", password: str | None = None, port: int = 22,
                   jump: str | None = None, command_timeout_s: float = 20.0) -> Linux:
    """Linux on the device over SSH (needs ``flipperone[ssh]``); connects on the first command."""
    shell = SshShell(SshSettings(host=host, user=user, password=password, port=port, jump=jump))
    return Linux(shell, command_timeout_s=command_timeout_s)
