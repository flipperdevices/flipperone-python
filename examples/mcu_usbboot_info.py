"""What the MCU's flash holds, from its USB bootloader (needs picotool; the MCU in its bootloader: ``power boot``)."""

from flipperone.mcu import usbboot

device = usbboot.wait_bootrom(timeout=20)
print(device.describe(), "(new chip)" if usbboot.is_new_chip(device) else "")
print(usbboot.Picotool().info(device))
