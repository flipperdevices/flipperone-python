# SPDX-License-Identifier: GPL-3.0-or-later
"""Errors raised by the library. Everything derives from :class:`FlipperOneError`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .transport.base import CommandResult


class FlipperOneError(Exception):
    """Base of every error the library raises."""


class TransportError(FlipperOneError):
    """A port, a connection or a stream failed."""


class PortNotFound(TransportError):
    """The port or device is not there (not plugged in, or in another mode)."""


class PortBusy(TransportError):
    """Another program holds the port exclusively."""


class ConnectError(TransportError):
    """An SSH connection could not be made."""


class CommandTimeout(TransportError):
    """A command on the device produced nothing within its timeout."""


class CommandFailed(FlipperOneError):
    """A command the caller asked to be checked exited with a non-zero code; carries the result."""

    def __init__(self, result: CommandResult):
        detail = (result.err or result.out).strip()[:400]
        super().__init__(f"'{result.command}' exited with {result.code}: {detail}")
        self.result = result


class CliError(FlipperOneError):
    """The text CLI of the MCU or of the Debug Probe answered unexpectedly."""


class SyncTimeout(CliError):
    """The prompt did not come in time; ``received`` holds what the device sent meanwhile."""

    def __init__(self, message: str, received: bytes = b""):
        super().__init__(message)
        self.received = received


class CommandNotFound(CliError):
    """The CLI does not know the command (another firmware?)."""


class UsageError(CliError):
    """The CLI answered with its usage text: wrong arguments, or a firmware that changed the command."""


class UnexpectedReply(CliError):
    """A command's reply could not be read."""


class ToolNotFound(FlipperOneError):
    """An external program the library drives (``picotool``, ``rockusb``) is not installed."""


class ToolFailed(FlipperOneError):
    """An external program exited with an error or did not finish in time."""
