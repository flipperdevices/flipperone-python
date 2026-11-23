import pytest

from flipperone.errors import AmbiguousDevice
from flipperone.probe import Probe, ProbeId, Role, probes, select
from flipperone.probe.ports import port, wait_port
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


def probe_ports(serial: str, chip: str) -> list[Port]:
    return [Port(f"/dev/cu.usbmodem{serial}{n}", f"/dev/cu.usbmodem{serial}{n}", serial, n, 0x37C1, 0xF131,
                 f"Flipper One Debug Probe {chip}") for n in (2, 4, 6, 8)]


ONE = probe_ports("f1_debug_4b30_", "D7DA0C50B04820F2")
TWO = probe_ports("f1_debug_d950_", "63E7482F2DB3DF2B")
OLD = probe_ports("flip_one_debug", "D7DA0C50B04820F2")      # firmware before 0.7.0


def test_ports_by_role():
    found = port(Role.PROBE_CLI, ONE)
    assert found is not None and found.interface == 8 and found.serial == "f1_debug_4b30_"
    assert port(Role.MCU_CLI, []) is None
    assert port(Role.MCU_CLI, OLD) is None                     # the old serial is not a probe here
    assert wait_port(Role.MCU_CLI, timeout=0, discover_fn=lambda: ONE) == ONE[1]


def test_several_probes_need_a_name():
    both = ONE + TWO
    assert probes(both) == [ProbeId("f1_debug_4b30_", "D7DA0C50B04820F2"),
                            ProbeId("f1_debug_d950_", "63E7482F2DB3DF2B")]
    with pytest.raises(AmbiguousDevice, match="several Debug Probes"):
        port(Role.MCU_CLI, both)
    for name in ("d950", "f1_debug_d950_", "63e7", "63E7482F2DB3DF2B"):
        assert port(Role.MCU_CLI, both, probe=name) == TWO[1]
    assert port(Role.MCU_CLI, both, probe="ffff") is None
    assert select([], None) is None
    no_chip = [Port("/dev/ttyACM0", "/dev/ttyACM0", "f1_debug_0001_", 2, 0x37C1, 0xF131, None)]
    assert probes(no_chip) == [ProbeId("f1_debug_0001_", None)]
    with pytest.raises(AmbiguousDevice, match="matches several"):
        select([ProbeId("f1_debug_aaaa_", "ABCD000000000000"), ProbeId("f1_debug_bbbb_", "ABCD111111111111")], "abcd")
