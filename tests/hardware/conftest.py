"""Tests on a real Flipper One: selected with ``-m hardware`` and skipped unless the device is described by the
``FLIPPERONE_*`` variables (see README.md here). Read-only: nothing on the device is changed."""

import os
from collections.abc import Iterator

import pytest

from flipperone import connect
from flipperone.linux import Linux
from flipperone.mcu import Mcu
from flipperone.probe import Probe

pytestmark = pytest.mark.hardware


def _env(name: str) -> str | None:
    return os.environ.get(f"FLIPPERONE_{name}") or None


@pytest.fixture(scope="session")
def mcu() -> Iterator[Mcu]:
    channel = _env("MCU")
    if channel not in ("usb", "probe"):
        pytest.skip("FLIPPERONE_MCU=usb|probe not set")
    device = connect.mcu_over_usb() if channel == "usb" else connect.mcu_over_probe()
    yield device
    device.close()


@pytest.fixture(scope="session")
def probe() -> Iterator[Probe]:
    if not _env("PROBE"):
        pytest.skip("FLIPPERONE_PROBE=1 not set")
    device = connect.probe_cli()
    yield device
    device.close()


@pytest.fixture(scope="session")
def linux() -> Iterator[Linux]:
    host = _env("SSH_HOST")
    if host is None:
        pytest.skip("FLIPPERONE_SSH_HOST not set")
    device = connect.linux_over_ssh(host, user=_env("SSH_USER") or "user", password=_env("SSH_PASSWORD"))
    yield device
    device.close()
