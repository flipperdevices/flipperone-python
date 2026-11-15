"""The MCU's firmware, uptime and heap, over its own USB port (Linux off) or the Debug Probe (``--probe``)."""

import sys

from flipperone import connect

with connect.mcu_over_probe() if "--probe" in sys.argv else connect.mcu_over_usb() as mcu:
    info = mcu.device_info()
    print("firmware:", info.get("rp2350_firmware_version"), info.get("rp2350_firmware_commit"))
    print("chip:    ", info.get("rp2350_hardware_uid"))
    print("uptime:  ", mcu.uptime(), "s")
    heap = mcu.free()
    print("heap:    ", heap.free, "free of", heap.total)
