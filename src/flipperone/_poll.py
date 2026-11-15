# SPDX-License-Identifier: GPL-3.0-or-later
"""Polling until a condition holds (internal)."""

from __future__ import annotations

import time
from collections.abc import Callable


def wait_until[T](probe: Callable[[], T | None], timeout: float | None = None, poll: float = 1.0,
                  sleep: Callable[[float], None] = time.sleep,
                  clock: Callable[[], float] = time.monotonic) -> T | None:
    """Call ``probe`` until it returns a truthy value and return that value; ``None`` once ``timeout`` (seconds)
    has passed. The first call is immediate; ``timeout=None`` waits forever."""
    deadline = None if timeout is None else clock() + timeout
    while True:
        result = probe()
        if result:
            return result
        if deadline is not None and clock() >= deadline:
            return None
        sleep(poll)
