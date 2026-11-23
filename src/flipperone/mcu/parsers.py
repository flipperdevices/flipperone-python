# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure functions turning the MCU CLI's text into values (formats from flipperone-mcu-firmware; each function names
the file its format string lives in).

Records are read tolerantly: a field the firmware no longer prints is ``None``, a new one is kept in ``raw``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .._text import strip_ansi

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_UPTIME = re.compile(r"Uptime: (\d+)h(\d+)m(\d+)s")
_SARADC_ID = re.compile(r"SARADC ID:\s*(\d+)")
_KEY_EVENT = re.compile(r"^key: (\S+) type: (\S+)$")
_TOUCH_EVENT = re.compile(r"^touch: (\S+) x=(-?\d+) y=(-?\d+) p=(-?\d+)$")
_RUNNING_APP = re.compile(r"^running app: (\S+)$", re.M)
_LISTED_APP = re.compile(r"^\s*(.+?) \((\S+)\)$")
_STARTED_APP = re.compile(r"^started .* \((\S+)\)$", re.M)
_STOPPED_APP = re.compile(r"^stop requested: (.+)$", re.M)
NO_APP = "no app is running"
TOUCH_NO_POSITION = 65535


def key_values(text: str) -> dict[str, str]:
    """Lines of ``printf("%-30s: %s")`` (``device_info``, ``power info``) as a dict; other lines are skipped."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(": ")
        if sep and key.strip():
            result[key.strip()] = value.strip()
    return result


def help_names(text: str) -> list[str]:
    """``help``: the command names between ``Available commands:`` and ``Find out more`` (cli_shell.c)."""
    names: list[str] = []
    inside = False
    for line in strip_ansi(text).splitlines():
        if line.startswith("Available commands:"):
            inside = True
            continue
        if line.startswith("Find out more"):
            break
        if inside:
            names.extend(line.split())
    return names


def uptime_seconds(text: str) -> int:
    """``Uptime: 1h2m3s`` (cli_commands_common.c) -> seconds."""
    m = _UPTIME.search(text)
    if m is None:
        raise ValueError(f"no uptime in {text!r}")
    h, mnt, s = (int(x) for x in m.groups())
    return h * 3600 + mnt * 60 + s


@dataclass(frozen=True)
class HeapStats:
    """``free`` (cli_commands_common.c), in bytes."""

    free: int | None
    total: int | None
    minimum: int | None
    max_block: int | None
    pool_free: int | None = None
    pool_max_block: int | None = None
    raw: dict[str, str] = field(default_factory=dict, compare=False)


def heap_stats(text: str) -> HeapStats:
    kv = key_values(text)
    if not kv:
        raise ValueError(f"free: nothing to read in {text!r}")
    return HeapStats(free=_int(kv.get("Free heap size")), total=_int(kv.get("Total heap size")),
                     minimum=_int(kv.get("Minimum heap size")), max_block=_int(kv.get("Maximum heap block")),
                     pool_free=_int(kv.get("Pool free")), pool_max_block=_int(kv.get("Maximum pool block")), raw=kv)


@dataclass(frozen=True)
class PowerInfo:
    """``power info`` (power_cli.c); units as printed there: mV, mA, %, degrees C."""

    state: str | None
    battery_level: int | None
    battery_voltage_mv: int | None
    battery_current_ma: int | None
    battery_ntc_c: float | None
    usb_voltage_mv: int | None
    usb_current_ma: int | None
    usb_current_limit_ma: int | None
    charger_enabled: bool | None
    charger_level_limit: int | None
    charger_current_limit_ma: int | None
    charger_temperature_c: float | None
    raw: dict[str, str] = field(default_factory=dict, compare=False)


def power_info(text: str) -> PowerInfo:
    kv = key_values(text)
    if not kv:
        raise ValueError(f"power info: nothing to read in {text!r}")
    enabled = _float(kv.get("charger.enabled"))
    return PowerInfo(
        state=kv.get("state"),
        battery_level=_int(kv.get("BAT.level")),
        battery_voltage_mv=_int(kv.get("BAT.voltage")),
        battery_current_ma=_int(kv.get("BAT.current")),
        battery_ntc_c=_float(kv.get("BAT.NTC")),
        usb_voltage_mv=_int(kv.get("USB.voltage")),
        usb_current_ma=_int(kv.get("USB.current")),
        usb_current_limit_ma=_int(kv.get("USB.current_limit")),
        charger_enabled=None if enabled is None else enabled != 0,
        charger_level_limit=_int(kv.get("charger.level_limit")),
        charger_current_limit_ma=_int(kv.get("charger.current_limit")),
        charger_temperature_c=_float(kv.get("charger.temperature")),
        raw=kv,
    )


def nvm_value(text: str, kind: str, key: str) -> int | bool | str:
    """``nvm get <i|u|b|s> <key>`` -> ``key: value``; ``Key <key> is missing`` -> ``KeyError``."""
    for line in text.splitlines():
        if line.startswith("Key ") and line.endswith("is missing"):
            raise KeyError(key)
        name, sep, value = line.partition(": ")
        if sep and name == key:
            if kind in ("i", "u"):
                return int(value)
            if kind == "b":
                return value.strip() == "true"
            return value
    raise ValueError(f"nvm get: unexpected reply {text!r}")


def saradc_id(text: str) -> int:
    """``saradc get_id``: ``Current SARADC ID: 1`` -> 1."""
    m = _SARADC_ID.search(text)
    if not m:
        raise ValueError(f"no SARADC ID in {text!r}")
    return int(m.group(1))


@dataclass(frozen=True)
class KeyEvent:
    """A key event of ``input dump`` (input_cli.c)."""

    key: str     # Up, Down, Left, Right, OK, Back, Sw, Key1, Key2, Power, Key4, Key5, PTT
    type: str    # Press, Release, Short, Long, Repeat


@dataclass(frozen=True)
class TouchEvent:
    """A touchpad event of ``input dump``; ``x`` and ``y`` are ``None`` when the firmware sends no position."""

    type: str    # Start, Move, End
    x: int | None
    y: int | None
    pressure: int


def input_event(line: str) -> KeyEvent | TouchEvent | None:
    """One line of ``input dump``; ``None`` for anything else (its banner, an echo)."""
    line = strip_ansi(line).strip()
    m = _KEY_EVENT.match(line)
    if m:
        return KeyEvent(m.group(1), m.group(2))
    m = _TOUCH_EVENT.match(line)
    if m:
        x, y = int(m.group(2)), int(m.group(3))
        missing = x == TOUCH_NO_POSITION and y == TOUCH_NO_POSITION
        return TouchEvent(m.group(1), None if missing else x, None if missing else y, int(m.group(4)))
    return None


def running_app(text: str) -> str | None:
    """``desktop get_run_app``: the running app's id, ``None`` on the desktop (desktop_cli.c)."""
    found = _RUNNING_APP.search(text)
    if found:
        return found.group(1)
    if NO_APP in text:
        return None
    raise ValueError(f"no app named in {text!r}")


def listed_apps(text: str) -> dict[str, str]:
    """``desktop list_apps``: app id -> name, in the firmware's order (desktop_cli.c)."""
    apps: dict[str, str] = {}
    for line in text.splitlines():
        found = _LISTED_APP.match(line)
        if found:
            apps[found.group(2)] = found.group(1)
    return apps


def started_app(text: str) -> str:
    """``desktop start_app``: the id of the app started; the firmware's refusal as the error (desktop_cli.c)."""
    found = _STARTED_APP.search(text)
    if found:
        return found.group(1)
    raise ValueError(text.strip() or "no reply")


def stopped_app(text: str) -> str | None:
    """``desktop stop_app``: the id of the app asked to exit, ``None`` when none ran (desktop_cli.c)."""
    found = _STOPPED_APP.search(text)
    if found:
        return found.group(1).strip()
    if NO_APP in text:
        return None
    raise ValueError(f"unexpected reply {text!r}")


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    m = _NUMBER.search(value)
    return float(m.group(0)) if m else None


def _int(value: str | None) -> int | None:
    number = _float(value)
    return None if number is None else int(number)
