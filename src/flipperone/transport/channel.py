# SPDX-License-Identifier: GPL-3.0-or-later
"""A socket-like object as a :class:`~flipperone.transport.base.Stream`."""

from __future__ import annotations

import contextlib
from typing import Any

from ..errors import TransportError


class ChannelStream:
    """A :class:`~flipperone.transport.base.Stream` over anything with ``send``, ``recv``, ``settimeout`` and
    ``close``: a socket, or the SSH channel of a command (:meth:`SshShell.open_stream
    <flipperone.transport.ssh.SshShell.open_stream>`). A timeout surfaces from it as ``TimeoutError``."""

    def __init__(self, channel: Any, name: str):
        self.channel = channel
        self._name = name
        self._open = True

    @property
    def name(self) -> str:
        return self._name

    def read(self, timeout: float) -> bytes:
        self._require()
        self.channel.settimeout(timeout)
        try:
            data: bytes = self.channel.recv(4096)
        except TimeoutError:
            return b""
        except OSError as e:
            if "timed out" in str(e):
                return b""
            raise TransportError(f"{self._name}: {e}") from None
        if data == b"" and getattr(self.channel, "closed", False):
            raise TransportError(f"{self._name}: the stream closed")
        return data

    def write(self, data: bytes) -> None:
        self._require()
        try:
            self.channel.sendall(data) if hasattr(self.channel, "sendall") else self.channel.send(data)
        except OSError as e:
            raise TransportError(f"{self._name}: {e}") from None

    def reset_input(self) -> None:
        while self.read(0.05):
            pass

    def close(self) -> None:
        if not self._open:
            return
        with contextlib.suppress(OSError):
            self.channel.close()
        self._open = False

    def _require(self) -> None:
        if not self._open:
            raise TransportError(f"{self._name} is closed")
