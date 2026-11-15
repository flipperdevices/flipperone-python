"""Rockchip devices in MaskROM or loader mode (needs rockusb)."""

from flipperone.maskrom import Rockusb

rockusb = Rockusb()
for device in rockusb.list():
    print(device.selector, device.soc, rockusb.mode(device) or "mode unknown")
