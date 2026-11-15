import pytest

from flipperone.errors import CliError
from flipperone.experimental import power_screens, screen
from flipperone.mcu import Mcu
from flipperone.testing import FakeCli

POWER_SHOW = """INA219:
  VSYS:  8.824V

BQ28Z620:
  SoH:                100%
  Control Status: 0x0203 QMAX VOK CHECKSUM_VALID SEC: Full_Access
INA219:
  VSYS:  8.796V
"""


def test_power_screens():
    frame = power_screens.first_frame(POWER_SHOW)
    got = {r.name: (r.value, r.units) for r in power_screens.power_readings(frame)}
    assert got["ina219_vsys"] == (8.824, "V") and got["bq28z620_soh"] == (100, "%")
    assert str(got["bq28z620_control_status"][0]).startswith("0x0203 QMAX")
    line = "Channel 0 (VDD_0V75_S3        ): \tBus Voltage: 0.746 V, \tCurrent: -0.003 A"
    readings = power_screens.consumption_readings(f"INA4230 0\n{line}\nINA4230 0\n")
    assert [(r.name, r.value) for r in readings] == [("vdd_0v75_s3_bus_voltage", 0.746),
                                                    ("vdd_0v75_s3_current", -0.003)]
    with pytest.raises(ValueError, match="no complete frame"):
        power_screens.first_frame("INA219:\n  VSYS: 8.8V\n")


def frame_message(width: int, height: int, data: bytes) -> bytes:
    def field(number: int, payload: bytes) -> bytes:
        return bytes([number << 3 | 2, len(payload)]) + payload
    inner = bytes([1 << 3, width, 2 << 3, height]) + field(5, data)
    message = field(1, inner)
    return bytes([len(message)]) + message


def test_screenshot_over_the_raw_session():
    pixels = bytes(range(6))
    stream = FakeCli({"rpc": b"\xfd" + frame_message(3, 2, pixels)})
    mcu = Mcu(stream, timeout_s=0.2, sync_timeout_s=0.2, settle_s=0, sleep=lambda s: None)
    shot = screen.screenshot(mcu, timeout=1)
    assert (shot.width, shot.height, shot.pixels) == (3, 2, pixels) and shot.png().startswith(b"\x89PNG")
    assert stream.written[-1] == b"\x03"     # the CLI was brought back to its prompt
    with pytest.raises(CliError):
        screen.frame_of(bytes([10, 4, 24, 1, 32, 0]))


def test_screen_frame_parsing_cropping_and_png():
    pixels = bytes(i % 256 for i in range(258)) * 2
    inner = b"\x08\x82\x02\x10\x02\x18\x00\x20\x00\x2a" + bytes([0x84, 0x04]) + pixels   # 258x2, data 516 bytes
    msg = b"\x0a" + bytes([len(inner) & 0x7F | 0x80, len(inner) >> 7]) + inner
    frame = screen.frame_of(msg)
    assert (frame.width, frame.height) == (258, 2)
    c = frame.cropped()
    assert (c.width, len(c.pixels)) == (256, 512) and c.pixels[:256] == bytes(range(256))
    png = c.png(3)
    assert png.startswith(b"\x89PNG") and int.from_bytes(png[16:20], "big") == 768
    assert screen.frame_of(b"\x22\x00") is None              # not a frame


def test_screen_reader_is_bounded():
    clock = iter([0, 0, 1, 2, 3])
    r = screen.Reader(lambda t: b"", deadline=2, clock=lambda: next(clock))
    with pytest.raises(CliError):
        r.until_byte(screen.READY)
