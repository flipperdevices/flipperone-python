# SPDX-License-Identifier: GPL-3.0-or-later
"""A serial port as a :class:`~flipperone.transport.base.Stream`, opened exclusively (pyserial)."""

from __future__ import annotations

import errno
import logging
import time
from collections.abc import Callable
from typing import Any

from serial import Serial, SerialException

from ..errors import PortBusy, PortNotFound, TransportError

log = logging.getLogger(__name__)

DEFAULT_BAUDRATE = 1500000      # the Debug Probe's UART bridges run at this rate; USB CDC ports ignore it
_BUSY_ERRNOS = {errno.EAGAIN, errno.EWOULDBLOCK, errno.EBUSY}
_RETRY_S = 0.2


class SerialStream:
    """A serial port, opened exclusively (``flock``, the lock terminal programs such as tio take too).

    ``dtr``: raised on open and lowered on close. The Flipper One's CDC ports start a CLI session when DTR rises;
    lowering it on close matters on the Debug Probe, which drives the MCU's UART while DTR is up.
    ``busy_timeout_s``: how long to retry a port another program holds (it may be handing it over) before
    :class:`~flipperone.errors.PortBusy`.
    """

    def __init__(self, path: str, *, baudrate: int = DEFAULT_BAUDRATE, dtr: bool = True,
                 busy_timeout_s: float = 0.0, serial_factory: Callable[..., Any] | None = None,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.path = path
        factory = serial_factory or Serial
        deadline = clock() + busy_timeout_s
        while True:
            try:
                self._ser: Any = factory(path, baudrate=baudrate, timeout=0.1, exclusive=True)
                break
            except SerialException as e:
                error = _open_error(path, e)
                if not isinstance(error, PortBusy) or clock() >= deadline:
                    raise error from None
                sleep(_RETRY_S)
        if dtr:
            self._ser.dtr = True
        self._dtr = dtr
        log.debug("%s: open", path)

    @property
    def name(self) -> str:
        return self.path

    @property
    def is_open(self) -> bool:
        return self._ser is not None

    def read(self, timeout: float) -> bytes:
        ser = self._require()
        ser.timeout = timeout
        try:
            data: bytes = ser.read(1)
            if data and ser.in_waiting:
                data += ser.read(ser.in_waiting)
        except (OSError, SerialException) as e:
            raise TransportError(f"{self.path}: {e}") from None
        return data

    def write(self, data: bytes) -> None:
        ser = self._require()
        try:
            ser.write(data)
            ser.flush()
        except (OSError, SerialException) as e:
            raise TransportError(f"{self.path}: {e}") from None

    def reset_input(self) -> None:
        self._require().reset_input_buffer()

    def close(self) -> None:
        if self._ser is None:
            return
        try:
            if self._dtr:
                self._ser.dtr = False
            self._ser.close()
        except (OSError, SerialException):
            pass        # the port may be gone already (the device rebooted)
        self._ser = None
        log.debug("%s: closed", self.path)

    def __enter__(self) -> SerialStream:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _require(self) -> Any:
        if self._ser is None:
            raise TransportError(f"{self.path} is closed")
        return self._ser


def _open_error(path: str, e: SerialException) -> TransportError:
    code = getattr(e, "errno", None)
    if code in _BUSY_ERRNOS or "exclusively lock" in str(e):
        return PortBusy(f"{path} is held by another program: {e}")
    if code == errno.ENOENT or "No such file" in str(e):
        return PortNotFound(f"{path}: no such port")
    return TransportError(f"cannot open {path}: {e}")
