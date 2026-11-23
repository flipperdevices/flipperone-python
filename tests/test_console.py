import itertools

import pytest

from flipperone.errors import CommandTimeout, TransportError
from flipperone.linux import Linux
from flipperone.transport.console import BEGIN, END, SerialShell

PROMPT = b"\x1b[?2004huser@flipperone-189a05:~$ "
BANNER = b"\x1b[47m\x1b[90m\r\nFlipper One CPU console, fixed baud rate: 1500000\r\n\x1b[0m"


class FakeConsole:
    """The CPU's console as the probe bridges it: Ctrl-C and Enter give a prompt; a framed command line gives its
    echo, the markers and the output from ``replies`` (command -> (output, exit code)); silent when ``off``."""

    def __init__(self, replies: dict[str, tuple[str, int]] | None = None, off: bool = False):
        self.replies = replies or {}
        self.off = off
        self.written: list[bytes] = []
        self.out = bytearray(BANNER)
        self.closed = False

    @property
    def name(self) -> str:
        return "console"

    def read(self, timeout: float) -> bytes:
        data = bytes(self.out)
        self.out.clear()
        return data

    def write(self, data: bytes) -> None:
        self.written.append(data)
        if self.off:
            return
        if data.startswith(b"\x03"):
            self.out += b"^C\r\n" + PROMPT
            return
        line = data.decode().rstrip("\r")
        command = line.split("( ", 1)[1].rsplit(" )", 1)[0] if "( " in line else line
        out, code = self.replies.get(command, ("", 0))
        self.out += line.encode() + b"\r\n" + BEGIN.encode() + b"\r\n"
        self.out += out.replace("\n", "\r\n").encode() + f"{END}{code}\r\n".encode() + PROMPT

    def reset_input(self) -> None:
        self.out.clear()

    def close(self) -> None:
        self.closed = True


def test_run_frames_a_command_and_takes_its_exit_code():
    console = FakeConsole({"uname -r": ("7.4.0-rc1\n", 0), "false": ("", 1), "printf x": ("x", 0)})
    shell = SerialShell(console)
    result = shell.run("uname -r", 5)
    assert (result.code, result.out, result.err) == (0, "7.4.0-rc1\n", "")
    assert shell.run("false", 5).code == 1
    lines: list[str] = []
    assert shell.run("printf x", 5, lines.append).out == "x\n" and lines == ["x"]   # no final newline: still read
    assert console.written[-1].startswith(b"stty -echo; echo " + BEGIN.encode() + b"; ( printf x ); echo ")
    assert Linux(shell).run("uname -r").out.strip() == "7.4.0-rc1"
    with pytest.raises(ValueError):
        shell.run("a\nb", 5)
    shell.close()
    assert console.closed


def test_a_silent_console_and_the_refused_operations():
    shell = SerialShell(FakeConsole(off=True), ready_timeout_s=0.3)
    assert shell.ready() == (False, False)              # the probe's banner from opening the port does not count

    class AtLogin(FakeConsole):
        def write(self, data: bytes) -> None:
            self.out += b"\r\nflipperone-189a05 login: "
    assert SerialShell(AtLogin(), ready_timeout_s=0.3).ready() == (False, True)
    with pytest.raises(TransportError, match="no shell prompt"):
        shell.run("true", 1)
    for refused in (lambda: shell.open_stream("cat"), lambda: shell.put(None, "x"),      # type: ignore[arg-type]
                    lambda: shell.get("x", None)):                                     # type: ignore[arg-type]
        with pytest.raises(TransportError, match="SSH"):
            refused()


def test_a_command_that_does_not_end_gets_ctrl_c():
    class Hanging(FakeConsole):
        def write(self, data: bytes) -> None:
            if data.startswith(b"stty"):
                self.written.append(data)
                return
            super().write(data)

    clock = itertools.count(0.0, 0.05)
    console = Hanging()
    shell = SerialShell(console, clock=lambda: next(clock))
    with pytest.raises(CommandTimeout):
        shell.run("sleep 100", 3)
    assert console.written[-1] == b"\x03"
