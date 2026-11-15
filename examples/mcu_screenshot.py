"""The device's screen as a PNG (experimental API)."""

from pathlib import Path

from flipperone import connect
from flipperone.experimental import screen

with connect.mcu_over_probe() as mcu:
    shot = screen.screenshot(mcu).cropped()
Path("screen.png").write_bytes(shot.png(scale=3))
print("screen.png", shot.width, "x", shot.height)
