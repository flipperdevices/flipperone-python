import subprocess
from pathlib import Path
from typing import Any

import pytest

from flipperone.errors import PortNotFound, ToolFailed, ToolNotFound
from flipperone.mcu import usbboot
from flipperone.transport import UsbDevice

BOOTROM = UsbDevice(0x37C1, 0xF102, 3, 12)


def picotool(out: str = "", code: int = 0) -> tuple[usbboot.Picotool, list[list[str]]]:
    calls: list[list[str]] = []

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, code, out, "error" if code else "")
    return usbboot.Picotool("picotool", runner=run), calls


def test_commands_select_the_device_and_report_failures(tmp_path: Path):
    tool, calls = picotool("Program Information\n none\n")
    assert tool.is_blank(BOOTROM)
    tool.load(BOOTROM, tmp_path / "fw.uf2")
    tool.erase_all(BOOTROM)
    assert calls[1] == ["picotool", "load", "-v", "-x", str(tmp_path / "fw.uf2"), "--vid", "0x37c1", "--pid", "0xf102"]
    assert calls[2][:3] == ["picotool", "erase", "-a"] and calls[3][:3] == ["picotool", "reboot", "-u"]
    failing, _ = picotool(code=1)
    with pytest.raises(ToolFailed, match="exit code 1: error"):
        failing.info(BOOTROM)
    assert failing.answers(BOOTROM) is False
    with pytest.raises(ToolNotFound):
        usbboot.Picotool(which=lambda name: None)


def test_wait_bootrom_skips_the_old_enumeration_and_gives_up():
    scans = iter([[BOOTROM], [UsbDevice(0x37C1, 0xF102, 3, 13)]])
    device = usbboot.wait_bootrom(5, previous=BOOTROM, ready=lambda d: True, find=lambda ids: next(scans),
                                  sleep=lambda s: None)
    assert device.address == 13
    assert usbboot.is_new_chip(UsbDevice(0x2E8A, 0x000F, 1, 1))
    with pytest.raises(PortNotFound, match="none ready"):
        usbboot.wait_bootrom(0, ready=lambda d: True, find=lambda ids: [], sleep=lambda s: None)
