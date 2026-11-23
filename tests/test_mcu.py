import pytest

from flipperone.errors import CliError, UnexpectedReply, UsageError
from flipperone.mcu import KeyEvent, Mcu, TouchEvent
from flipperone.testing import FakeCli
from replies import COMMANDS

FAST = {"timeout_s": 0.2, "sync_timeout_s": 0.2, "settle_s": 0, "sleep": lambda s: None}
DUMP = (b"input dump\r\nPress CTRL+C to stop\r\n"
        b"key: Up type: Press\r\nkey: Up type: Short\r\nkey: Up type: Release\r\n"
        b"touch: Start x=308 y=190 p=583\r\ntouch: Move x=400 y=300 p=900\r\ntouch: End x=65535 y=65535 p=0\r\n")


def mcu(**streams):
    stream = FakeCli(dict(COMMANDS), streams or None)
    return Mcu(stream, **FAST), stream


def test_wrapped_commands():
    m, stream = mcu()
    assert m.device_info()["rp2350_firmware_version"] == "r175"
    assert m.uptime() == 5556
    assert m.free().total == 496788
    assert m.power_info().battery_level == 96
    assert "power" in m.help()
    assert m.dmesg().splitlines()[1] == "68 [I][Flipper] Startup complete"
    assert m.nvm_list() == ["LSKV", "LedBacklightTime"]
    assert m.nvm_get("u", "LedBacklightTime") == 10000
    assert m.saradc_get_id() == 1
    with pytest.raises(KeyError):
        m.nvm_get("s", "nope")
    with pytest.raises(ValueError):
        m.nvm_get("x", "k")
    m.input_send("Back", "Short")
    assert stream.lines[-1] == "input send Back Short"


def test_led():
    m, stream = mcu()
    m.led("Power", "green")
    m.led(4, 1)
    m.led("lineAllOff")
    assert stream.lines[-3:] == ["led 4 1", "led 4 1", "led 16"]
    with pytest.raises(ValueError, match="needs a colour"):
        m.led("Power")
    with pytest.raises(ValueError, match="out of range"):
        m.led(99, 0)
    with pytest.raises(UsageError):
        m.led("Net", "red")          # the fake answers `led 0 0` with the usage text


def test_unexpected_reply():
    m, stream = mcu()
    stream.commands["uptime"] = "garbage"
    with pytest.raises(UnexpectedReply, match="'uptime'"):
        m.uptime()


def test_input_dump_gives_events_and_stops_when_asked():
    m, _ = mcu(**{"input dump": DUMP})
    seen: list[object] = []

    def handler(event: KeyEvent | TouchEvent | None) -> bool:
        if event is not None:
            seen.append(event)
        return isinstance(event, TouchEvent) and event.type == "Move"

    assert m.input_dump(handler, timeout=5) is True
    assert seen == [KeyEvent("Up", "Press"), KeyEvent("Up", "Short"), KeyEvent("Up", "Release"),
                    TouchEvent("Start", 308, 190, 583), TouchEvent("Move", 400, 300, 900)]
    assert m.uptime() == 5556


def test_power_reboot_ends_the_session_and_never_sends_ctrl_d():
    m, stream = mcu()
    m.power_reboot()
    assert stream.written[-1] == b"power reboot\r" and stream.closed and not m.is_open
    assert not any(b"\x04" in w for w in stream.written)
    with pytest.raises(CliError):
        m.uptime()


class StuckInRpc(FakeCli):
    """A CLI left inside an RPC session: text is not answered until the session is closed in that protocol."""

    def __init__(self, **kwargs: object):
        super().__init__(banner=b"", **kwargs)      # type: ignore[arg-type]
        self.stuck = True
        self._rpc = bytearray()

    def write(self, data: bytes) -> None:
        if self.stuck:
            self.written.append(bytes(data))
            self._rpc += data
            if b"\x02\x32\x00" in self._rpc:
                self.stuck = False
            return
        super().write(data)


def test_sync_closes_a_left_over_rpc_session():
    stream = StuckInRpc(commands={"uptime": "Uptime: 0h0m5s"})
    m = Mcu(stream, **FAST)
    assert m.uptime() == 5
    assert stream.written[:3] == [b"\x03", b"\x02\x32\x00", b"\x03"]
    plain = FakeCli(dict(COMMANDS))
    Mcu(plain, **FAST)
    assert b"\x02\x32\x00" not in b"".join(plain.written)          # a healthy session gets Ctrl-C only


def test_desktop_apps():
    state = {"app": None}

    def desktop(line: str) -> str:
        words = line.split()
        if words[1] == "get_run_app":
            return f"running app: {state['app']}\r\n" if state["app"] else "no app is running\r\n"
        if words[1] == "list_apps":
            return "Available apps:\r\n\tSelf check (self_check)\r\n\tCPU App (cpu_app_start)\r\n"
        if words[1] == "start_app":
            if state["app"]:
                return f"failed to start {words[2]}: {state['app']} is already running\r\n"
            if words[2] not in ("cpu_app_start", "self_check"):
                return f"app not found: {words[2]}\r\n"
            state["app"] = words[2]
            return f"started CPU App ({words[2]})\r\n"
        app, state["app"] = state["app"], None
        return f"stop requested: {app}\r\n" if app else "no app is running\r\n"

    m, _ = mcu()
    m._stream.commands["desktop"] = desktop       # type: ignore[union-attr]
    assert m.desktop_run_app() is None
    assert m.desktop_list_apps() == {"self_check": "Self check", "cpu_app_start": "CPU App"}
    assert m.desktop_start_app("cpu_app_start") == "cpu_app_start"
    assert m.desktop_run_app() == "cpu_app_start"
    with pytest.raises(CliError, match="already running"):
        m.desktop_start_app("self_check")
    assert m.desktop_stop_app() == "cpu_app_start"
    assert m.desktop_stop_app() is None
    with pytest.raises(CliError, match="app not found: nope"):
        m.desktop_start_app("nope")
    with pytest.raises(ValueError):
        m.desktop_start_app("two words")
