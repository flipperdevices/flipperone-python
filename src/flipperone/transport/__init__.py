# SPDX-License-Identifier: GPL-3.0-or-later
"""How the library reaches the device: byte streams (:class:`Stream`) and command shells (:class:`Shell`), with
implementations over serial ports, SSH and any socket-like object, and the lookup of USB serial ports and devices."""

from .base import CommandResult, Shell, Stream
from .channel import ChannelStream
from .ports import Port, discover, find, wait_for
from .serial import DEFAULT_BAUDRATE, SerialStream
from .ssh import SshSettings, SshShell
from .usb import UsbDevice, devices, usb_bcd

__all__ = [
    "DEFAULT_BAUDRATE", "ChannelStream", "CommandResult", "Port", "SerialStream", "Shell", "SshSettings", "SshShell",
    "Stream", "UsbDevice", "devices", "discover", "find", "usb_bcd", "wait_for",
]
