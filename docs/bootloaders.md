# Bootloaders

## The MCU's USB bootloader (`flipperone.mcu.usbboot`)

The RP2350 boot ROM enumerates as `37c1:f102` (white-labelled in OTP) or `2e8a:000f` (a new chip). A running firmware
goes there with `Mcu.power_boot()`.

```python
from flipperone.mcu import usbboot

mcu.power_boot()
device = usbboot.wait_bootrom(timeout=20)          # enumerated and answering picotool
tool = usbboot.Picotool()                          # picotool on PATH, or Picotool("/path/to/picotool")
tool.info(device); tool.is_blank(device)
tool.load(device, Path("fw.uf2"))                  # write, verify, start
tool.erase_all(device)                             # about 190 s; then wait_bootrom(previous=device)
tool.uf2_combine(table, firmware, Path("out.uf2"), partition=0)
```

Every picotool command has a time limit; failures are `ToolFailed`, a missing picotool `ToolNotFound`.

## The CPU in MaskROM (`flipperone.maskrom`)

```python
from flipperone.maskrom import Rockusb

rockusb = Rockusb()                                # rockusb on PATH, or Rockusb("/path/to/rockusb")
device = rockusb.wait(timeout=10)
rockusb.mode(device)                               # "maskrom" or "loader", from bcdUSB
rockusb.download_boot(device, Path("loader.bin"))  # refused in loader mode
rockusb.run("chip-info", device=device)            # any other rockusb command
```
