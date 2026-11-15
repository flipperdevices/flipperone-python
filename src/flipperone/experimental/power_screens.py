# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental: no stability promise. The MCU's live ``power`` screens (``power show``, ``power consumption``):
they redraw themselves until stopped and are read by their layout, which changes with the firmware.

``power show``: INA219, the charger BQ25798 with its status and fault registers, the gauge BQ28Z620 with its state
of health; ``power consumption``: every INA4230 channel by rail. ``power_readings`` also reads ``power info``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..mcu import Mcu

SCREEN_S = 1.5   # the screens redraw about every 0.5 s: two frames start within this


def power_show(mcu: Mcu, seconds: float = SCREEN_S) -> str:
    """One frame of ``power show``, as printed."""
    return first_frame(mcu.stream("power show", seconds).text)


def power_consumption(mcu: Mcu, seconds: float = SCREEN_S) -> str:
    """One frame of ``power consumption``, as printed."""
    return first_frame(mcu.stream("power consumption", seconds).text)


@dataclass(frozen=True)
class Reading:
    """One value a status screen prints: its name (lower case, ``_`` for anything else), the value (a number where
    the screen prints one, else the text as printed) and the units printed after the number."""
    name: str
    value: float | int | str
    units: str | None = None


_VALUE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*([A-Za-z%]+)?$")


def _key(*parts: str) -> str:
    return "_".join(p for p in (re.sub(r"[^a-z0-9]+", "_", part.lower()).strip("_") for part in parts) if p)


def _reading(name: str, text: str) -> Reading:
    text = text.strip()
    m = _VALUE.match(text)
    if m is None:
        return Reading(name, text)
    number = float(m.group(1))
    return Reading(name, int(number) if number.is_integer() and "." not in m.group(1) else number, m.group(2))


def first_frame(text: str) -> str:
    """The first complete frame of a status screen that redraws itself (``power show``, ``power consumption``): a
    frame starts with the screen's first line, so the text up to that line's next appearance. A single frame (the
    stream stopped inside the second one or before it) is refused: it may be cut short."""
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        raise ValueError("no output")
    try:
        end = lines.index(lines[0], 1)
    except ValueError:
        raise ValueError("no complete frame: the screen was not redrawn while it was read") from None
    return "\n".join(lines[:end])


def power_readings(text: str) -> list[Reading]:
    """``power info`` (``BAT.level : 96%``) and a frame of ``power show`` (sections ``INA219:``, ``BQ2579X:``,
    ``BQ28Z620:`` with indented ``VSYS:  8.824V`` lines; status registers as ``0x0F VBUS_PRESENT ...`` text)."""
    readings: list[Reading] = []
    section = ""
    for line in text.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        if not value.strip() and not line.startswith((" ", "\t")):
            section = key.strip()
            continue
        readings.append(_reading(_key(section, key), value))
    if not readings:
        raise ValueError(f"no readings in {text[:200]!r}")
    return readings


_CHANNEL = re.compile(r"^Channel\s+\d+\s+\((?P<rail>[^)]*)\):(?P<values>.*)$")


def consumption_readings(text: str) -> list[Reading]:
    """A frame of ``power consumption``: per INA4230 channel ``Channel 0 (VDD_0V75_S3 ): Bus Voltage: 0.746 V,
    Shunt Voltage: -0.150 mV, Current: -0.003 A, Power: 0.003 W``, named after the rail."""
    readings: list[Reading] = []
    for line in text.splitlines():
        m = _CHANNEL.match(line.strip())
        if m is None:
            continue
        for item in m.group("values").split(","):
            key, sep, value = item.partition(":")
            if sep:
                readings.append(_reading(_key(m.group("rail"), key), value))
    if not readings:
        raise ValueError(f"no channels in {text[:200]!r}")
    return readings
