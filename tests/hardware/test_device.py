import pytest

from flipperone.linux import Linux
from flipperone.mcu import Mcu
from flipperone.probe import INPUT_PINS, Probe

pytestmark = pytest.mark.hardware


def test_mcu_reads(mcu: Mcu):
    info = mcu.device_info()
    assert info.get("rp2350_hardware_uid") and info.get("rp2350_firmware_version")
    assert mcu.uptime() > 0
    assert "power" in mcu.help()
    heap = mcu.free()
    assert heap.free and heap.total and heap.free <= heap.total
    power = mcu.power_info()
    assert power.state and power.battery_level is not None
    assert isinstance(mcu.nvm_list(), list)
    assert mcu.dmesg()


def test_probe_reads_an_input(probe: Probe):
    assert probe.gpio_get(INPUT_PINS[0]) in (0, 1)


def test_linux_commands_and_files(linux: Linux):
    assert linux.run("uname -s", check=True).out.strip() == "Linux"
    files = linux.read_many(["/etc/os-release", "/proc/device-tree/model", "/nonexistent"])
    assert "ID=" in (files["/etc/os-release"] or "") and files["/nonexistent"] is None
    assert linux.exists("/sys/class")
