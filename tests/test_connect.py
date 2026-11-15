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
