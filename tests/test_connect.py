import re

import pytest

from flipperone import connect
from flipperone.errors import PortNotFound


def test_serial_opener_reports_a_missing_port(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(connect, "wait_for", lambda *a, **k: None)
    with pytest.raises(PortNotFound, match="USB serial 'flip_one_debug', interface 4"):
        connect.serial_opener("flip_one_debug", 4)()


def test_linux_over_ssh_connects_lazily():
    linux = connect.linux_over_ssh("10.0.0.1", password="x")
    assert linux.shell.settings.describe() == "user@10.0.0.1:22"      # type: ignore[attr-defined]


def test_probe_opener_reports_a_missing_probe(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(connect, "wait_port", lambda *a, **k: None)
    with pytest.raises(PortNotFound, match="no Debug Probe 'd950' with its MCU_LOG port"):
        connect.probe_opener(connect.Role.MCU_LOG, probe="d950")()
    with pytest.raises(PortNotFound, match=r"USB serial 'f1_debug_.*'"):
        monkeypatch.setattr(connect, "wait_for", lambda *a, **k: None)
        connect.serial_opener(re.compile(r"f1_debug_[0-9a-f]{4}_"), 4)()
