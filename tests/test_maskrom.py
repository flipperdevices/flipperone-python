import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from flipperone.errors import ToolFailed, ToolNotFound
from flipperone.maskrom import Device, MaskromError, Rockusb, mode_from_bcd, parse_list

LIST = "Available rockchip devices:\n* Bus 2 Device 5 ID 2207:350e\n* Bus 1 Device 3 ID 1234:5678\n"


def runner(replies: dict[str, tuple[int, str]]):
    calls: list[list[str]] = []

    def run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        code, out = replies.get(argv[-1] if argv[-1] != "list" else "list", (0, ""))
        return subprocess.CompletedProcess(list(argv), code, out, "")
    return run, calls


def test_parse_list_and_mode():
    assert parse_list(LIST)[0] == Device(2, 5, 0x2207, 0x350E)
    assert parse_list(LIST)[0].soc == "RK3576" and parse_list(LIST)[0].selector == "2:5"
    assert mode_from_bcd(0x0200) == "maskrom" and mode_from_bcd(0x0201) == "loader"


def test_list_keeps_rockchip_and_download_boot_checks_the_mode(tmp_path: Path):
    run, calls = runner({"list": (0, LIST)})
    rk = Rockusb("rockusb", runner=run, usb_bcd_fn=lambda b, a: 0x0200)
    devices = rk.list()
    assert devices == [Device(2, 5, 0x2207, 0x350E)]
    rk.download_boot(devices[0], tmp_path / "loader.bin")
    assert calls[-1] == ["rockusb", "-d", "2:5", "download-boot", str(tmp_path / "loader.bin")]
    loader = Rockusb("rockusb", runner=run, usb_bcd_fn=lambda b, a: 0x0201)
    with pytest.raises(MaskromError, match="runs a loader"):
        loader.download_boot(devices[0], tmp_path / "loader.bin")


def test_errors():
    with pytest.raises(ToolNotFound):
        Rockusb(which=lambda name: None)
    run, _ = runner({"list": (1, "")})
    with pytest.raises(ToolFailed):
        Rockusb("rockusb", runner=run).list()
