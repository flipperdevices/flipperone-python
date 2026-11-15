# SPDX-License-Identifier: GPL-3.0-or-later
"""Stand-ins for tests of code that uses the library, no device needed: :class:`FakeShell` for
:class:`~flipperone.linux.Linux` and :class:`FakeCli`, a :class:`~flipperone.transport.base.Stream` that behaves
like the firmware's CLI, for :class:`~flipperone.mcu.Mcu` and :class:`~flipperone.probe.Probe`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .transport.base import CommandResult

Reply = str | CommandResult | Callable[[str], "CommandResult | str | None"]


@dataclass
class FakeShell:
    """Canned replies by exact command (a string, a result, or a callable of the command), an optional catch-all
    ``handler``, files by remote path, and a record of every command run. A command without a reply exits 127."""

    replies: dict[str, Reply] = field(default_factory=dict)
    handler: Callable[[str], CommandResult | str | None] | None = None
    files: dict[str, bytes] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    streams: dict[str, FakeCli] = field(default_factory=dict)    # command -> the stream open_stream returns
    closed: bool = False

    def run(self, command: str, timeout: float, on_line: Callable[[str], None] | None = None) -> CommandResult:
        result = self._reply(command)
        if on_line is not None:
            for line in result.out.splitlines():
                on_line(line)
        return result

    def open_stream(self, command: str) -> FakeCli:
        self.commands.append(command)
        return self.streams.get(command) or FakeCli(name=command)

    def put(self, local: Path, remote: str) -> None:
        self.files[remote] = Path(local).read_bytes()

    def get(self, remote: str, local: Path) -> None:
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        Path(local).write_bytes(self.files[remote])

    def close(self) -> None:
        self.closed = True

    def _reply(self, command: str) -> CommandResult:
        self.commands.append(command)
        reply = self.replies.get(command)
        if callable(reply):
            reply = reply(command)
        if reply is None and self.handler is not None:
            reply = self.handler(command)
        if reply is None:
            return CommandResult(command, 127, "", f"fake: no reply for {command!r}")
        if isinstance(reply, CommandResult):
            return reply
        return CommandResult(command, 0, reply, "")


PROMPT = b"\r\ncontrol>: "
BANNER = b"\r\nWelcome to Flipper One Command Line Interface!\r\n" + PROMPT
CliHandler = Callable[[str], bytes | str]


class FakeCli:
    """A :class:`~flipperone.transport.base.Stream` that behaves like the firmware's shell: echoes printable bytes,
    runs a line on CR (``commands``: the whole line or its first word -> reply, or a callable of the line), answers
    an unknown command like the firmware, prints ``^C`` and the prompt on Ctrl-C, and stops a command of ``streams``
    (line -> what it prints until stopped) on Ctrl-C."""

    def __init__(self, commands: dict[str, bytes | str | CliHandler] | None = None,
                 streams: dict[str, bytes] | None = None, *, prompt: bytes = PROMPT, banner: bytes = BANNER,
                 name: str = "fake"):
        self.commands = commands or {}
        self.streams = streams or {}
        self.prompt = prompt
        self.lines: list[str] = []          # every line run
        self.written: list[bytes] = []
        self.closed = False
        self._name = name
        self._out = bytearray(banner)
        self._line = bytearray()
        self._streaming: str | None = None

    @property
    def name(self) -> str:
        return self._name

    def read(self, timeout: float) -> bytes:
        data = bytes(self._out)
        self._out.clear()
        return data

    def write(self, data: bytes) -> None:
        self.written.append(bytes(data))
        for byte in data:
            self._feed(byte)

    def reset_input(self) -> None:
        self._out.clear()

    def close(self) -> None:
        self.closed = True

    def push(self, data: bytes) -> None:
        """Make the device "send" ``data`` (an event a test wants read)."""
        self._out += data

    def _feed(self, byte: int) -> None:
        if self._streaming is not None:
            if byte == 0x03:
                self._streaming = None
                self._out += self.prompt
            return
        if byte == 0x03:
            self._line.clear()
            self._out += b"^C" + self.prompt
        elif byte == 0x0D:
            line = self._line.decode("ascii")
            self._line.clear()
            self._out += b"\r\n"
            if line.strip():
                self.lines.append(line)
                self._execute(line.strip())
            if self._streaming is None:
                self._out += self.prompt
        elif 0x20 <= byte <= 0x7E:
            self._line.append(byte)
            self._out.append(byte)

    def _execute(self, line: str) -> None:
        if line in self.streams:
            self._streaming = line
            self._out += self.streams[line]
            return
        handler = self.commands.get(line)
        if handler is None:
            handler = self.commands.get(line.split(" ", 1)[0])
        if handler is None:
            name = line.split(" ", 1)[0]
            self._out += f"\x1b[31mcould not find command `{name}`, try `help`\x1b[0m".encode()
            return
        reply = handler(line) if callable(handler) else handler
        self._out += reply.encode("ascii") if isinstance(reply, str) else reply
