# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental: buttons and the touchpad injected through the MCU's RPC session (``rpc``), the way the screen is read
(:mod:`.screen`). Events go to the MCU's input service as a physical button's or the touchpad's would, so they reach
whatever owns the screen: an MCU app, the desktop, or Linux.

The wire format (flipperone-mcu-protobuf, ``rpc.proto``): ``RpcMessage.button_event`` (field 2: ``button`` 1,
``action`` 2) and ``RpcMessage.touch_event`` (field 3: ``type`` 1, ``x`` 2, ``y`` 3, ``pressure`` 4), proto3 varints.

The firmware derives ``short``, ``long`` and ``repeat`` from how long a physical button is held, but not for injected
events: a click is sent as ``press``, ``short``, ``release`` (what the input service itself sends), a hold as
``press``, ``long``, ``repeat``\\ s, ``release``. Firmware before the protocol's ``SHORT``/``LONG``/``REPEAT``
(r175, 13f32b2, for one) logs ``Unknown action`` for those and drops them; ``press`` and ``release`` work there, and
most of the MCU's UI acts on ``press``.

Each call opens one RPC session and closes it, whatever happens; the CLI is busy meanwhile.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Iterable

from ..mcu import Mcu
from .screen import CLOSE, READY, Reader

BUTTONS = {"ok": 0, "back": 1, "key1": 2, "key2": 3, "power": 4, "key4": 5, "key5": 6, "sw": 7, "down": 8,
           "right": 9, "left": 10, "up": 11, "ptt": 12}     # Flipper_One_Input_Button; "power" is the third key
ACTIONS = {"press": 0, "release": 1, "short": 2, "long": 3, "repeat": 4}
TOUCH_TYPES = {"start": 0, "move": 1, "end": 2}
TOUCH_MAX_X, TOUCH_MAX_Y = 1023, 767         # input_touch.h: x left to right, y top to bottom
TOUCH_MAX_PRESSURE = 16383
FIELD_BUTTON_EVENT = 2
FIELD_TOUCH_EVENT = 3
GAP_S = 0.05                 # between the events of one press, as the input service spaces them


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def message(field: int, payload: bytes) -> bytes:
    """``RpcMessage`` with ``payload`` in ``field``, length-delimited as the session sends it."""
    body = varint(field << 3 | 2) + varint(len(payload)) + payload
    return varint(len(body)) + body


def _fields(*pairs: tuple[int, int]) -> bytes:
    """Varint fields; proto3 leaves zeros out."""
    return b"".join(varint(number << 3) + varint(value) for number, value in pairs if value)


def button_event(button: str, action: str) -> bytes:
    """The message of one button event (``BUTTONS``, ``ACTIONS``)."""
    if button not in BUTTONS:
        raise ValueError(f"unknown button {button!r}; one of {tuple(BUTTONS)}")
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}; one of {tuple(ACTIONS)}")
    return message(FIELD_BUTTON_EVENT, _fields((1, BUTTONS[button]), (2, ACTIONS[action])))


def touch_event(kind: str, x: int, y: int, pressure: int) -> bytes:
    """The message of one touch event (``TOUCH_TYPES``; x 0..1023, y 0..767, pressure 0..16383)."""
    if kind not in TOUCH_TYPES:
        raise ValueError(f"unknown touch type {kind!r}; one of {tuple(TOUCH_TYPES)}")
    if not (0 <= x <= TOUCH_MAX_X and 0 <= y <= TOUCH_MAX_Y and 0 <= pressure <= TOUCH_MAX_PRESSURE):
        raise ValueError(f"touch at ({x}, {y}) pressure {pressure} is out of range")
    return message(FIELD_TOUCH_EVENT, _fields((1, TOUCH_TYPES[kind]), (2, x), (3, y), (4, pressure)))


def click_events(button: str, hold_s: float = 0.0, repeats: int = 0) -> list[tuple[bytes, float]]:
    """(message, pause after it) for one button: a click, or a hold of ``hold_s`` with ``repeats`` repeats."""
    if hold_s <= 0:
        return [(button_event(button, "press"), GAP_S), (button_event(button, "short"), 0.0),
                (button_event(button, "release"), GAP_S)]
    events = [(button_event(button, "press"), hold_s), (button_event(button, "long"), GAP_S)]
    events += [(button_event(button, "repeat"), GAP_S)] * repeats
    return [*events, (button_event(button, "release"), GAP_S)]


def swipe_events(start: tuple[int, int], end: tuple[int, int] | None = None, pressure: int = 8000,
                 steps: int = 10, step_s: float = 0.02) -> list[tuple[bytes, float]]:
    """(message, pause after it) for a tap at ``start``, or a swipe to ``end`` in ``steps`` moves."""
    (x0, y0) = start
    events = [(touch_event("start", x0, y0, pressure), step_s)]
    if end is not None:
        (x1, y1) = end
        for i in range(1, steps + 1):
            events.append((touch_event("move", x0 + (x1 - x0) * i // steps, y0 + (y1 - y0) * i // steps, pressure),
                           step_s))
        x0, y0 = x1, y1
    return [*events, (touch_event("end", x0, y0, 0), GAP_S)]


def send(mcu: Mcu, events: Iterable[tuple[bytes, float]], timeout: float = 5.0,
         sleep: Callable[[float], None] = time.sleep) -> None:
    """Open an RPC session, send ``events`` (message, pause after it) and close the session, whatever happens."""
    with mcu.raw_session("rpc") as session:
        try:
            Reader(session.read, time.monotonic() + timeout).until_byte(READY)
            for data, pause in events:
                session.write(data)
                if pause:
                    sleep(pause)
        finally:
            with contextlib.suppress(Exception):
                session.write(CLOSE)


def press(mcu: Mcu, *buttons: str, hold_s: float = 0.0, repeats: int = 0, gap_s: float = 0.15,
          sleep: Callable[[float], None] = time.sleep) -> None:
    """Click ``buttons`` in order, ``gap_s`` apart, in one session; ``hold_s`` holds each instead (two buttons
    cannot be down at once)."""
    events: list[tuple[bytes, float]] = []
    for i, button in enumerate(buttons):
        events += click_events(button, hold_s, repeats)
        if i < len(buttons) - 1:
            events[-1] = (events[-1][0], gap_s)
    send(mcu, events, sleep=sleep)


def action(mcu: Mcu, button: str, act: str, sleep: Callable[[float], None] = time.sleep) -> None:
    """One raw event (``press``, ``release``, ``short``, ``long``, ``repeat``)."""
    send(mcu, [(button_event(button, act), 0.0)], sleep=sleep)


def touch(mcu: Mcu, x: int, y: int, to: tuple[int, int] | None = None, *, pressure: int = 8000, steps: int = 10,
          sleep: Callable[[float], None] = time.sleep) -> None:
    """Tap the touchpad at (``x``, ``y``), or swipe from there ``to`` another point. What a point means on screen is
    the app's business (the Touchpad Test maps only the middle of the range onto its drawing)."""
    send(mcu, swipe_events((x, y), to, pressure, steps), sleep=sleep)
