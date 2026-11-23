import re
from types import SimpleNamespace

from flipperone.transport.ports import (
    Port,
    discover,
    find,
    interface_from_by_id,
    interface_from_location,
    interface_from_mac_name,
    wait_for,
)


def fake_port(device, serial, location=None, name=None):
    return SimpleNamespace(device=device, name=name or device.rsplit("/", 1)[-1], serial_number=serial,
                           location=location, vid=0x37C1, pid=0xF131, product="Flipper One Debug Probe X")


MAC_PORTS = [
    fake_port("/dev/cu.usbmodemflip_one_debug8", "flip_one_debug", "2-1.4.4.1.1"),
    fake_port("/dev/cu.usbmodemflip_one_debug2", "flip_one_debug", "2-1.4.4.1.1"),
    fake_port("/dev/cu.usbmodemflip_one_mcu1", "flip_one_mcu", "2-1.4.4.4"),
    fake_port("/dev/cu.usbmodemflip_one_debug6", "flip_one_debug", "2-1.4.4.1.1"),
    fake_port("/dev/cu.usbmodemflip_one_debug4", "flip_one_debug", "2-1.4.4.1.1"),
    SimpleNamespace(device="/dev/cu.Bluetooth-Incoming-Port", name="cu.Bluetooth-Incoming-Port",
                    serial_number=None, location=None, vid=None, pid=None, product=None),
]

LINUX_PORTS = [
    fake_port("/dev/ttyACM3", "flip_one_debug", "3-1:1.7"),       # as on the bench: the communication interfaces
    fake_port("/dev/ttyACM0", "flip_one_debug", "3-1:1.1"),
    fake_port("/dev/ttyACM2", "flip_one_debug", "3-1:1.5"),
    fake_port("/dev/ttyACM1", "flip_one_debug", "3-1:1.3"),
]
LINUX_BY_ID = {
    f"/dev/ttyACM{i}": f"/dev/serial/by-id/usb-Flipper_FZCO_Flipper_One_Debug_Probe_X_flip_one_debug-if0{n}-port0"
    for i, n in enumerate((1, 3, 5, 7))
}


def test_interface_from_mac_name():
    assert interface_from_mac_name("cu.usbmodemflip_one_debug6", "flip_one_debug") == 6
    assert interface_from_mac_name("cu.usbmodemflip_one_mcu1", "flip_one_mcu") == 1
    assert interface_from_mac_name("cu.usbmodemflip_one_debug", "flip_one_debug") is None
    assert interface_from_mac_name("cu.usbmodem12345", None) == 12345


def test_interface_from_location():
    assert interface_from_location("1-2.3:1.3") == 3
    assert interface_from_location("1-2.3:1.10") == 10
    assert interface_from_location("2-1.4.4.1.1") is None
    assert interface_from_location(None) is None


def test_interface_from_by_id():
    assert interface_from_by_id("/dev/serial/by-id/usb-X_flip_one_debug-if04-port0") == 4
    assert interface_from_by_id("/dev/serial/by-id/usb-X_flip_one_debug-if10") == 10
    assert interface_from_by_id("/dev/ttyACM0") is None


def test_discover_macos_orders_by_serial_and_interface():
    ports = discover(MAC_PORTS, by_id={}, platform="darwin")
    assert [(p.serial, p.interface) for p in ports] == [
        ("flip_one_debug", 2), ("flip_one_debug", 4), ("flip_one_debug", 6), ("flip_one_debug", 8),
        ("flip_one_mcu", 1),
    ]
    assert all(p.stable_path == p.device for p in ports)


def test_discover_linux_prefers_by_id_paths():
    ports = discover(LINUX_PORTS, by_id=LINUX_BY_ID, platform="linux")
    assert [p.interface for p in ports] == [2, 4, 6, 8]
    assert ports[1].device == "/dev/ttyACM1"
    assert ports[1].stable_path.endswith("-if03-port0")


def test_discover_linux_falls_back_to_by_id_for_interface():
    ports = [fake_port("/dev/ttyACM1", "flip_one_debug", location=None)]
    (port,) = discover(ports, by_id=LINUX_BY_ID, platform="linux")
    assert port.interface == 4


def test_discover_linux_numbers_like_macos():
    """The MCU's own port: communication interface 0 on Linux, ``flip_one_mcu1`` on macOS: both 1."""
    (port,) = discover([fake_port("/dev/ttyACM4", "flip_one_mcu", "3-7:1.0")], by_id={}, platform="linux")
    assert port.interface == 1


def test_find():
    ports = discover(MAC_PORTS, by_id={}, platform="darwin")
    assert find(ports, "flip_one_debug", 6).device == "/dev/cu.usbmodemflip_one_debug6"
    assert find(ports, "flip_one_mcu").device == "/dev/cu.usbmodemflip_one_mcu1"
    assert find(ports, "flip_one_debug", 3) is None
    assert find([], "flip_one_debug", 2) is None


def test_port_matches():
    p = Port("/dev/x", "/dev/x", "s", 2, None, None, None)
    assert p.matches("s", 2) and p.matches("s", None)
    assert not p.matches("s", 4) and not p.matches("t", 2)


def test_wait_for_returns_port_when_it_appears():
    mac = discover(MAC_PORTS, by_id={}, platform="darwin")
    scans = iter([[], [], mac])
    slept = []
    port = wait_for("flip_one_debug", 6, poll=0.5, discover_fn=lambda: next(scans), sleep=slept.append)
    assert port.device == "/dev/cu.usbmodemflip_one_debug6"
    assert slept == [0.5, 0.5]


def test_wait_for_times_out():
    now = [0.0]

    def clock():
        return now[0]

    def sleep(s):
        now[0] += s

    assert wait_for("flip_one_debug", 2, timeout=2.5, poll=1.0, discover_fn=list, sleep=sleep, clock=clock) is None
    assert now[0] == 3.0


def test_find_by_pattern():
    ports = [Port("/dev/ttyACM0", "/dev/ttyACM0", "f1_debug_4b30_", 4, 0x37C1, 0xF131, None),
             Port("/dev/ttyACM1", "/dev/ttyACM1", None, 4, None, None, None)]
    assert find(ports, re.compile(r"f1_debug_[0-9a-f]{4}_"), 4) == ports[0]
    assert find(ports, re.compile(r"f1_debug_"), 4) is None              # the whole serial must match
    assert find(ports, "f1_debug_4b30_", 4) == ports[0]
