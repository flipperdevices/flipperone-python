# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental: no stability promise (the RPC is young; the few messages needed are encoded by hand).

The device's screen as the MCU's GUI holds it, over the CLI's RPC session (``rpc``): the "virtual display" stream of
``applications/services/rpc/rpc_screen_stream.c``, one frame taken. Frames of Linux (flipctl, the Flipper OS installer)
pass through the same frame buffer, so this sees whatever the panel shows.

The wire format (flipperone-mcu-protobuf, ``rpc.proto``): after ``rpc`` the MCU sends the ready marker ``0xFD``; each
message is a length-delimited ``RpcMessage``. ``StartVirtualDisplayRequest`` (field 4) starts frames
(``RpcMessage.frame``, field 1: ``Frame`` width 1, height 2, encoding 3, pixel_format 4, data 5; PLAIN, L8), then
``StopVirtualDisplayRequest`` (5) and ``RpcSessionCloseRequest`` (6) end the session and the text CLI is back. The few
messages needed are encoded by hand: no protobuf library.
"""

from __future__ import annotations

import contextlib
import struct
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass

from ..errors import CliError
from ..mcu import Mcu

READY = 0xFD
START = b"\x02\x22\x00"      # RpcMessage{start_virtual_display_request {}}, length-delimited
STOP = b"\x02\x2a\x00"       # RpcMessage{stop_virtual_display_request {}}
CLOSE = b"\x02\x32\x00"      # RpcMessage{rpc_session_close_request {}}
VISIBLE_WIDTH = 256          # the panel; the frame buffer is 258 wide, its last 2 columns are not shown


@dataclass(frozen=True)
class Screen:
    width: int
    height: int
    pixels: bytes            # L8, row after row

    def cropped(self, width: int = VISIBLE_WIDTH) -> Screen:
        if self.width <= width:
            return self
        rows = (self.pixels[y * self.width:y * self.width + width] for y in range(self.height))
        return Screen(width, self.height, b"".join(rows))

    def png(self, scale: int = 1) -> bytes:
        """A grayscale PNG, each pixel ``scale`` times larger (no smoothing)."""
        rows = []
        for y in range(self.height):
            row = self.pixels[y * self.width:(y + 1) * self.width]
            wide = bytes(b for b in row for _ in range(scale))
            rows += [b"\x00" + wide] * scale

        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        header = struct.pack(">IIBBBBB", self.width * scale, self.height * scale, 8, 0, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
                + chunk(b"IEND", b""))


def varint(buf: bytes, i: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        if i >= len(buf):
            raise ValueError("truncated varint")
        b = buf[i]
        i += 1
        value |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return value, i


def fields(msg: bytes) -> dict[int, int | bytes]:
    """The top-level fields of a protobuf message (varints and length-delimited only)."""
    out: dict[int, int | bytes] = {}
    i = 0
    while i < len(msg):
        tag, i = varint(msg, i)
        if tag & 7 == 0:
            out[tag >> 3], i = varint(msg, i)
        elif tag & 7 == 2:
            n, i = varint(msg, i)
            out[tag >> 3] = msg[i:i + n]
            i += n
        else:
            raise ValueError(f"unexpected wire type {tag & 7}")
    return out


def frame_of(message: bytes) -> Screen | None:
    """The frame an ``RpcMessage`` carries, or None for any other message."""
    top = fields(message)
    inner = top.get(1)
    if not isinstance(inner, bytes):
        return None
    f = fields(inner)
    width, height, data = f.get(1), f.get(2), f.get(5, b"")
    if not isinstance(data, bytes):
        raise CliError("malformed screen frame: no pixel data")
    if f.get(3, 0) != 0 or f.get(4, 0) != 0:
        raise CliError(f"screen frame in an encoding this tool does not read (encoding {f.get(3)!r}, "
                       f"format {f.get(4)!r})")
    if not isinstance(width, int) or not isinstance(height, int) or len(data) != width * height:
        raise CliError(f"malformed screen frame: {width!r}x{height!r}, {len(data)} bytes")
    return Screen(width, height, bytes(data))


class Reader:
    """Bytes from a link (``read(timeout)``), buffered, every read bounded by one deadline."""

    def __init__(self, read: Callable[[float], bytes], deadline: float, clock: Callable[[], float] = time.monotonic):
        self.read, self.deadline, self.clock, self.buf = read, deadline, clock, bytearray()

    def take(self, n: int) -> bytes:
        while len(self.buf) < n:
            remaining = self.deadline - self.clock()
            if remaining <= 0:
                raise CliError("the screen stream stopped answering")
            self.buf += self.read(min(remaining, 0.2))
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def until_byte(self, marker: int) -> None:
        while True:
            if marker in self.buf:
                del self.buf[:self.buf.index(marker) + 1]
                return
            remaining = self.deadline - self.clock()
            if remaining <= 0:
                raise CliError("no RPC session: the ready marker did not come")
            self.buf += self.read(min(remaining, 0.2))

    def message(self) -> bytes:
        length = shift = 0
        while True:
            b = self.take(1)[0]
            length |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                return self.take(length)


def screenshot(mcu: Mcu, timeout: float = 10.0) -> Screen:
    """One frame of the device's screen: an RPC session is opened with ``rpc``, the virtual display started for one
    frame, and the session closed whatever happens, so the text CLI is back. The CLI is busy meanwhile."""
    with mcu.raw_session("rpc") as session:
        reader = Reader(session.read, time.monotonic() + timeout)
        try:
            reader.until_byte(READY)
            session.write(START)
            while True:
                frame = frame_of(reader.message())
                if frame is not None:
                    return frame
        finally:
            for request in (STOP, CLOSE):
                with contextlib.suppress(Exception):
                    session.write(request)
