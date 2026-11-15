# SPDX-License-Identifier: GPL-3.0-or-later
"""The Flipper One MCU (RP2350) over its text CLI."""

from __future__ import annotations

from collections.abc import Callable

from .._cli import CliDevice
from ..errors import UnexpectedReply
from . import parsers
from .parsers import HeapStats, KeyEvent, PowerInfo, TouchEvent

# Arguments of the ``led`` command, in the firmware's index order (led_cli.c).
LED_TYPES = ("Net", "WiFi", "Eth2", "Eth1", "Power", "BatteryOutline", "BatteryWatt1", "BatteryWatt2",
             "BatteryWatt3", "BatteryWatt4", "UsbCharging", "UsbWatt1", "UsbWatt2", "UsbWatt3", "UsbWatt4",
             "BatteryCenter", "LineAllOff")
LED_COLORS = ("red", "green", "blue", "yellow", "orange", "light_blue", "black")
LED_ALL_OFF = "LineAllOff"    # takes no colour
NVM_KINDS = ("i", "u", "b", "s")
KEYS = ("Key1", "Key2", "Power", "Key4", "Key5", "Back", "Up", "Down", "Right", "Left", "OK", "PTT", "Sw")
KEY_TYPES = ("Press", "Release", "Short", "Long", "Repeat")


class Mcu(CliDevice):
    """The MCU's command-line interface over a :class:`~flipperone.transport.base.Stream`.

    ``connect`` is an open stream, or a callable returning a new one (then :meth:`reconnect` works after
    :meth:`power_reboot`). Ready-made: :func:`flipperone.connect.mcu_over_usb`,
    :func:`~flipperone.connect.mcu_over_probe`.
    The session is brought to the prompt on construction with Ctrl-C; it is never ended with Ctrl-D or ``exit``,
    which stops the CLI on a UART until the MCU restarts.

    Methods are named after the commands they run (:meth:`power_info` runs ``power info``); any other command goes
    through :meth:`run` (or :meth:`stream` / :meth:`watch` for the ones that keep printing).
    """

    def help(self) -> list[str]:
        """The command names the firmware has."""
        return parsers.help_names(self._text("help"))

    def device_info(self) -> dict[str, str]:
        """``device_info``: the firmware (``rp2350_firmware_*``), the chip (``rp2350_hardware_uid``) and more."""
        return self._parse("device_info", parsers.key_values)

    def uptime(self) -> int:
        """Seconds since the MCU started."""
        return self._parse("uptime", parsers.uptime_seconds)

    def free(self) -> HeapStats:
        """The heap: free, total, the lowest free since start, the largest block."""
        return self._parse("free", parsers.heap_stats)

    def dmesg(self) -> str:
        """The MCU's log ring buffer, as printed."""
        return self._text("dmesg")

    def power_info(self) -> PowerInfo:
        """Battery, USB input and charger as the MCU reads them."""
        return self._parse("power info", parsers.power_info)

    def power_reboot(self) -> None:
        """Restart the MCU (the whole device is powered off and on). The session ends: call :meth:`reconnect`."""
        self.send_line("power reboot")
        self._sleep(0.1)    # let the line leave before the port goes away
        self.close()

    def power_boot(self) -> None:
        """Restart the MCU into its USB bootloader (the RP2350 boot ROM, see :mod:`flipperone.mcu.usbboot`). The
        session ends; nothing answers on the CLI until a firmware runs again."""
        self.send_line("power boot")
        self._sleep(0.1)
        self.close()

    def saradc_get_id(self) -> int:
        """The board's hardware ID, from its ID resistor."""
        return self._parse("saradc get_id", parsers.saradc_id)

    def nvm_list(self) -> list[str]:
        """The keys stored in the MCU's non-volatile memory."""
        return [line.strip() for line in self._text("nvm list").splitlines() if line.strip()]

    def nvm_get(self, kind: str, key: str) -> int | bool | str:
        """One NVM value read as ``kind``: ``i`` (signed), ``u`` (unsigned), ``b`` (bool), ``s`` (string). The NVM
        keeps no type: the same bytes read differently. ``KeyError`` when the key is missing."""
        if kind not in NVM_KINDS:
            raise ValueError(f"kind must be one of {NVM_KINDS}, not {kind!r}")
        return self._parse(f"nvm get {kind} {key}", lambda text: parsers.nvm_value(text, kind, key))

    def input_send(self, key: str, type_: str) -> None:
        """Inject one key event as if the hardware sent it (``KEYS``, ``KEY_TYPES``). A press an app reacts to is
        usually ``Press``, ``Short``, ``Release`` in that order. A name the firmware does not know raises
        :class:`~flipperone.errors.UsageError`."""
        self._text(f"input send {key} {type_}")

    def input_dump(self, handler: Callable[[KeyEvent | TouchEvent | None], bool], timeout: float) -> bool:
        """Every key and touchpad event as the MCU sees it (debounced, before Linux or any app). ``handler`` gets
        each event, and ``None`` about every 0.1 s of quiet, and returns True to stop. Returns whether it stopped
        (False: ``timeout`` ended the dump); the CLI is back at its prompt either way."""
        def on_line(line: str) -> bool:
            event = parsers.input_event(line) if line else None
            if line and event is None:
                return False    # the banner, an echo
            return bool(handler(event))
        return self.watch("input dump", on_line, timeout)

    def led(self, led: int | str, color: int | str | None = None) -> None:
        """Set one LED (a ``LED_TYPES`` name or index) to a colour (a ``LED_COLORS`` name or index);
        ``LineAllOff`` takes no colour."""
        index = _index(led, LED_TYPES, "led")
        if LED_TYPES[index] == LED_ALL_OFF:
            self._text(f"led {index}")
            return
        if color is None:
            raise ValueError(f"led {LED_TYPES[index]} needs a colour, one of {LED_COLORS}")
        self._text(f"led {index} {_index(color, LED_COLORS, 'color')}")

    def _parse[T](self, line: str, parser: Callable[[str], T]) -> T:
        text = self._text(line)
        try:
            return parser(text)
        except ValueError as e:
            raise UnexpectedReply(f"'{line}': {e}") from None


def _index(value: int | str, names: tuple[str, ...], what: str) -> int:
    if isinstance(value, int):
        if not 0 <= value < len(names):
            raise ValueError(f"{what} index {value} out of range 0..{len(names) - 1}")
        return value
    lowered = [n.lower() for n in names]
    if value.lower() not in lowered:
        raise ValueError(f"unknown {what} {value!r}; one of {names}")
    return lowered.index(value.lower())
