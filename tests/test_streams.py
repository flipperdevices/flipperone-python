import pytest
from serial import SerialException

from flipperone.errors import PortBusy, PortNotFound, TransportError
from flipperone.linux import Linux
from flipperone.testing import FakeCli, FakeShell
from flipperone.transport import ChannelStream, SerialStream, Stream


class FakeSerial:
    def __init__(self, port: str, **kwargs: object):
        self.port, self.kwargs = port, kwargs
        self.dtr = False
        self.timeout = None
        self.closed = False
        self.out = bytearray(b"hello")
        self.written = b""

    @property
    def in_waiting(self) -> int:
        return len(self.out)

    def read(self, n: int = 1) -> bytes:
        data = bytes(self.out[:n])
        del self.out[:n]
        return data

    def write(self, data: bytes) -> None:
        self.written += data

    def flush(self) -> None:
        pass

    def reset_input_buffer(self) -> None:
        self.out.clear()

    def close(self) -> None:
        self.closed = True


def test_serial_stream_opens_exclusively_raises_and_lowers_dtr():
    made: list[FakeSerial] = []
    stream = SerialStream("/dev/x", serial_factory=lambda p, **k: made.append(FakeSerial(p, **k)) or made[-1])
    ser = made[0]
    assert isinstance(stream, Stream) and ser.kwargs["exclusive"] is True and ser.dtr is True
    assert stream.read(0.1) == b"hello" and stream.read(0.1) == b""
    stream.write(b"x\r")
    assert ser.written == b"x\r"
    stream.close()
    assert ser.dtr is False and ser.closed and not stream.is_open
    stream.close()
    with pytest.raises(TransportError, match="closed"):
        stream.read(0.1)


def test_serial_stream_busy_is_retried_then_reported():
    attempts: list[int] = []

    def locked(*a: object, **k: object) -> FakeSerial:
        attempts.append(1)
        raise SerialException(35, "Could not exclusively lock port /dev/x")

    with pytest.raises(PortBusy):
        SerialStream("/dev/x", busy_timeout_s=0.05, serial_factory=locked, sleep=lambda s: None)
    assert len(attempts) > 1
    missing = SerialException(2, "could not open port /dev/y: [Errno 2] No such file or directory")
    missing.errno = 2
    with pytest.raises(PortNotFound):
        SerialStream("/dev/y", serial_factory=lambda *a, **k: (_ for _ in ()).throw(missing))


class Channel:
    def __init__(self) -> None:
        self.timeout = None
        self.closed = False
        self.sent = b""
        self.inbox = [b"abc"]

    def settimeout(self, t: float) -> None:
        self.timeout = t

    def recv(self, n: int) -> bytes:
        if not self.inbox:
            raise TimeoutError
        return self.inbox.pop(0)

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def close(self) -> None:
        self.closed = True


def test_channel_stream():
    channel = Channel()
    stream = ChannelStream(channel, "dut:/dev/ttyS1")
    assert stream.name == "dut:/dev/ttyS1" and stream.read(0.5) == b"abc" and channel.timeout == 0.5
    assert stream.read(0.1) == b""
    stream.write(b"\x03")
    assert channel.sent == b"\x03"
    stream.close()
    assert channel.closed


def test_linux_open_stream_with_sudo():
    shell = FakeShell()
    stream = Linux(shell).open_stream("cat /dev/ttyS1", sudo=True)
    assert isinstance(stream, FakeCli) and shell.commands == ["sudo -n sh -c 'cat /dev/ttyS1'"]
