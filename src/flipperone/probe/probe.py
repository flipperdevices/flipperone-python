# SPDX-License-Identifier: GPL-3.0-or-later
"""The Debug Probe's own CLI (its port :attr:`Role.PROBE_CLI <flipperone.probe.ports.Role>`)."""

from __future__ import annotations

from .._cli import CliDevice
from ..errors import UnexpectedReply

# Pins of the probe's ``gpio`` command: the reset lines are open-drain outputs (0 holds the chip in reset,
# 1 releases it), the rest inputs.
RESET_PINS = ("mcu_reset", "cpu_reset")
INPUT_PINS = ("mcu_m40", "cpu_d2", "cpu_d3")


class Probe(CliDevice):
    """The Debug Probe's CLI over a :class:`~flipperone.transport.base.Stream` (see
    :func:`flipperone.connect.probe_cli`); any command goes through :meth:`run`."""

    def gpio_get(self, pin: str) -> int:
        """The level of an input pin (``INPUT_PINS``), 0 or 1."""
        text = self._text(f"gpio {pin}")
        digits = [c for c in text.split()[-1:] if c in ("0", "1")] if text.split() else []
        if not digits:
            raise UnexpectedReply(f"gpio {pin}: no level in {text!r}")
        return int(digits[0])

    def gpio_set(self, pin: str, value: int) -> None:
        """Drive an output pin (``RESET_PINS``): 0 asserts the reset, 1 releases it."""
        if value not in (0, 1):
            raise ValueError("value must be 0 or 1")
        self._text(f"gpio {pin} {value}")

    def reset(self, chip: str, hold_s: float = 0.1) -> None:
        """Pulse a chip's reset line: ``chip`` is ``mcu`` or ``cpu``. The MCU's reset restarts only the MCU."""
        pin = f"{chip}_reset"
        if pin not in RESET_PINS:
            raise ValueError(f"chip must be 'mcu' or 'cpu', not {chip!r}")
        self.gpio_set(pin, 0)
        self._sleep(hold_s)
        self.gpio_set(pin, 1)
