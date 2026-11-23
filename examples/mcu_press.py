"""Open the MCU's power menu, take a screenshot, close it again (experimental API)."""

from pathlib import Path

from flipperone import connect
from flipperone.experimental import rpc_input, screen

with connect.mcu_over_probe() as mcu:
    rpc_input.press(mcu, "power")
    Path("menu.png").write_bytes(screen.screenshot(mcu).cropped().png(scale=3))
    rpc_input.press(mcu, "back")
print("menu.png")
