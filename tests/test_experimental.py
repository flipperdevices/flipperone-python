import itertools

import pytest

from flipperone.errors import CliError
from flipperone.experimental import host, power_screens, rpc_input, screen
from flipperone.mcu import Mcu
from flipperone.testing import FakeCli
from flipperone.transport.console import SerialShell

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


def test_rpc_input_messages():
    assert rpc_input.button_event("ok", "press") == b"\x02\x12\x00"                   # zeros are left out
    assert rpc_input.button_event("back", "short") == b"\x06\x12\x04\x08\x01\x10\x02"
    assert rpc_input.touch_event("move", 300, 2, 8000) == bytes.fromhex("0c1a0a080110ac02180220c03e")
    with pytest.raises(ValueError):
        rpc_input.button_event("key3", "press")
    with pytest.raises(ValueError):
        rpc_input.touch_event("start", 1024, 0, 1)
    click = [m for m, _ in rpc_input.click_events("up")]
    assert click == [rpc_input.button_event("up", a) for a in ("press", "short", "release")]
    hold = [m for m, _ in rpc_input.click_events("back", hold_s=0.5, repeats=2)]
    assert hold == [rpc_input.button_event("back", a) for a in ("press", "long", "repeat", "repeat", "release")]
    swipe = rpc_input.swipe_events((0, 0), (100, 50), steps=2)
    touch = rpc_input.touch_event
    assert [m for m, _ in swipe] == [touch("start", 0, 0, 8000), touch("move", 50, 25, 8000),
                                     touch("move", 100, 50, 8000), touch("end", 100, 50, 0)]


def test_rpc_input_over_the_raw_session():
    stream = FakeCli({"rpc": b"\xfd"})
    mcu = Mcu(stream, timeout_s=0.2, sync_timeout_s=0.2, settle_s=0, sleep=lambda s: None)
    rpc_input.press(mcu, "down", "ok", sleep=lambda s: None)
    sent = b"".join(stream.written)
    assert rpc_input.button_event("down", "press") in sent and rpc_input.button_event("ok", "release") in sent
    assert screen.CLOSE in sent and stream.written[-1] == b"\x03"
    rpc_input.touch(mcu, 10, 20, sleep=lambda s: None)
    rpc_input.action(mcu, "power", "long", sleep=lambda s: None)
    assert rpc_input.button_event("power", "long") in b"".join(stream.written)


def test_host_parsing():
    scan = ("Scanning bootdev 'ufshcd.bootdev':\n  0  efi_mgr ...\n"
            "  1  bls  /loader/entries/1-flipperos-minimal-7.4.conf\n"
            "  2  bls  /loader/entries/2-flipperos-desktop-7.4.conf\n(2 bootflows, 2 valid)\n")
    entries = host.boot_entries(scan)
    assert entries == ["minimal-7.4", "desktop-7.4"]
    assert host.entry_position(2, entries) == 2 and host.entry_position("DESK", entries) == 2
    for wrong in (3, "7.4", "router"):
        with pytest.raises(host.HostError):
            host.entry_position(wrong, entries)
    assert host.uptime_s("[  12.3] usb 1-1: new device\n123.45\n") == 123.45
    with pytest.raises(host.HostError):
        host.uptime_s("nothing")


class Device:
    """The MCU's desktop and the CPU's console sharing one power state, for the host flows."""

    PROMPT = b"user@flipperone:~$ "
    SCAN = (b"U-Boot 2025.10\r\n  1  bls  /loader/entries/1-flipperos-minimal.conf\r\n"
            b"  2  bls  /loader/entries/2-flipperos-desktop.conf\r\n(2 bootflows, 2 valid)\r\n")

    AUTO = (b"[    0.000000] Booting Linux on physical CPU 0x0\r\n[    2.1] usb 1-1: new device\r\n"
            b"\x1b[?1000lBooting Desktop\r\nflipperone login: user (automatic login)\r\n")

    def __init__(self, app: str | None = None, linux: bool = False, uptime: float = 100.0, menu: bool = True):
        self.app, self.linux, self.uptime, self.menu = app, linux, uptime, menu
        self.out = bytearray()
        self.chosen: bytes | None = None
        self.written: list[bytes] = []

    # the MCU's desktop command
    def desktop(self, line: str) -> str:
        words = line.split()
        if words[1] == "get_run_app":
            return f"running app: {self.app}\r\n" if self.app else "no app is running\r\n"
        if words[1] == "start_app":
            self.app = words[2]
            if not self.linux and self.menu:
                self.out += self.SCAN                  # powered: U-Boot scans and waits in its menu
            elif not self.linux:
                self.out += self.AUTO + self.PROMPT    # a release image boots its default by itself
                self.linux = True
            return f"started X ({words[2]})\r\n"
        app, self.app = self.app, None
        self.linux = False                             # the app cuts the CPU's power on its way out
        return f"stop requested: {app}\r\n"

    # the CPU's console as a Stream
    name = "console"

    def read(self, timeout: float) -> bytes:
        data = bytes(self.out)
        self.out.clear()
        return data

    def write(self, data: bytes) -> None:
        self.written.append(data)
        if self.app is None and not self.linux:
            return                                     # off: silent
        if data.startswith(b"\x03"):
            if self.linux:
                self.out += b"^C\r\n" + self.PROMPT
        elif data.endswith(b"\r") and self.chosen is None and not self.linux:
            self.chosen, self.linux = data, True
            self.out += b"Booting: desktop\r\n" + self.PROMPT
        elif b"poweroff" in data:
            self.out += b"[  OK  ] Reached target Power-Off.\r\nreboot: Power down\r\n"
            self.linux, self.app = False, None
        elif b"( " in data:
            command = data.decode().split("( ", 1)[1].rsplit(" )", 1)[0]
            self.uptime += 5
            out = f"{self.uptime:.2f}\r\n" if "uptime" in command else ""
            self.out += f"__FLIPPERONE_BEGIN__\r\n{out}__FLIPPERONE_END__0\r\n".encode() + self.PROMPT

    def reset_input(self) -> None:
        self.out.clear()

    def close(self) -> None:
        pass


def host_pair(device: Device) -> tuple[Mcu, SerialShell]:
    commands = {"desktop": device.desktop, "dmesg": "1 [I][Flipper] Startup complete\r\n"}
    mcu = Mcu(FakeCli(commands), timeout_s=0.2, sync_timeout_s=0.2, settle_s=0, sleep=lambda s: None)
    ticks = itertools.count(0.0, 0.05)
    return mcu, SerialShell(device, ready_timeout_s=0.3, clock=lambda: next(ticks))


def fast() -> dict[str, object]:
    ticks = itertools.count(0.0, 0.01)
    return {"sleep": lambda s: None, "clock": lambda: next(ticks)}


def test_host_state():
    for device, expected in ((Device(), host.HostState.OFF), (Device("cpu_app_start", True), host.HostState.UP),
                             (Device(None, True), host.HostState.UP_NO_HOST_APP),
                             (Device("cpu_app_maskrom"), host.HostState.MASKROM)):
        assert host.state(*host_pair(device)) == expected


def test_host_start_cold_and_stop():
    device = Device()
    mcu, console = host_pair(device)
    started = host.start(mcu, console, "desktop", **fast())          # type: ignore[arg-type]
    assert started == host.Started(["minimal", "desktop"], 2)
    assert host.start(*host_pair(Device()), **fast()).entry == 1     # type: ignore[arg-type]
    assert device.chosen == host.DOWN + b"\r" and device.linux
    with pytest.raises(host.HostError, match="powered already"):
        host.start(mcu, console, **fast())                           # type: ignore[arg-type]
    assert host.stop(mcu, console, **fast()) is True                 # type: ignore[arg-type]
    assert not device.linux and device.app is None
    assert host.stop(mcu, console, **fast()) is False                # type: ignore[arg-type]


def test_host_attach_and_hard_stop():
    device = Device(None, linux=True)                                # the MCU was reset while Linux ran
    mcu, console = host_pair(device)
    assert host.start(mcu, console, **fast()).attached               # type: ignore[arg-type]
    assert device.app == "cpu_app_start"
    assert host.stop(mcu, console, hard=True, **fast()) is True      # type: ignore[arg-type]
    assert not device.linux
    with pytest.raises(host.HostError, match="runs app 'self_check'"):
        host.start(*host_pair(Device("self_check")), **fast())       # type: ignore[arg-type]


def test_host_start_an_image_that_boots_by_itself():
    device = Device(menu=False)
    mcu, console = host_pair(device)
    console.ready()
    typed = len(device.written)
    started = host.start(mcu, console, **fast())                      # type: ignore[arg-type]
    assert started == host.Started([], None, booted="Desktop") and device.linux
    assert device.written[typed + 1:] == []                           # one probe for a shell, then nothing: no keys
                                                                      # into the boot
    with pytest.raises(host.HostError, match=r"no boot menu to choose 'router'.*booted Desktop"):
        host.start(*host_pair(Device(menu=False)), "router", **fast())  # type: ignore[arg-type]


def test_console_ready_ignores_the_probes_banner_and_old_output():
    device = Device()                                                # off: only the probe's banner, from opening
    device.out += b"\x1b[47mFlipper One CPU console, fixed baud rate: 1500000\r\n\x1b[0m"
    assert host.state(*host_pair(device)) == host.HostState.OFF
