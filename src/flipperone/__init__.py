# SPDX-License-Identifier: GPL-3.0-or-later
"""Work with a Flipper One from Python.

- :mod:`flipperone.mcu` — the MCU's CLI (:class:`~flipperone.mcu.Mcu`) and its USB bootloader;
- :mod:`flipperone.linux` — Linux on the main board (:class:`~flipperone.linux.Linux`);
- :mod:`flipperone.probe` — the Debug Probe: its ports and its CLI;
- :mod:`flipperone.maskrom` — the CPU in MaskROM (``rockusb``);
- :mod:`flipperone.transport` — streams and shells the above run over;
- :mod:`flipperone.connect` — ready-made pairings (``mcu_over_usb()``, ``linux_over_ssh()``...);
- :mod:`flipperone.experimental` — no stability promise.
"""

from .errors import FlipperOneError

__version__ = "0.1.0"
__all__ = ["FlipperOneError", "__version__"]
