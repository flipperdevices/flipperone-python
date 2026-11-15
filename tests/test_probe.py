import pytest

from flipperone.probe import Probe, Role
from flipperone.probe.ports import port
from flipperone.testing import FakeCli
from flipperone.transport import Port

FAST = {"timeout_s": 0.2, "sync_timeout_s": 0.2, "settle_s": 0, "sleep": lambda s: None}
GPIO_USAGE = ("Usage:\r\ngpio <pin_name> <0|1>\t - Set gpio value, if pin is output\r\n"
              "gpio <pin_name>\t\t - Read gpio value, if pin is input\r\n")


def gpio(line: str) -> str:
    words = line.split()
    if len(words) == 1:
        return GPIO_USAGE
    if len(words) == 2:
        return f"Pin {words[1]} => 1"          # as the probe's firmware v0.5.0 answers
    return ""


def test_gpio_and_reset():
    stream = FakeCli({"gpio": gpio}, prompt=b"\r\ndebug_probe>: ")
    probe = Probe(stream, **FAST)
    assert probe.gpio_get("mcu_m40") == 1
    probe.reset("mcu")
    assert stream.lines[-2:] == ["gpio mcu_reset 0", "gpio mcu_reset 1"]
    with pytest.raises(ValueError):
        probe.reset("gpu")
    with pytest.raises(ValueError):
        probe.gpio_set("cpu_reset", 2)


def test_ports_by_role():
    ports = [Port(f"/dev/cu.usbmodemflip_one_debug{n}", f"/dev/cu.usbmodemflip_one_debug{n}", "flip_one_debug", n,
                  0x37C1, 0xF131, "Debug Probe") for n in (2, 4, 6, 8)]
    found = port(Role.PROBE_CLI, ports)
    assert found is not None and found.interface == 8
    assert port(Role.MCU_CLI, []) is None
