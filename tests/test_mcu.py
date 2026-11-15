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
