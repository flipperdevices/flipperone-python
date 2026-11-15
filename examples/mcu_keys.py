"""Print the keys and touches the MCU sees for 10 seconds, then press Back once (an injected event)."""

from flipperone import connect
from flipperone.mcu import KeyEvent, TouchEvent


def show(event: KeyEvent | TouchEvent | None) -> bool:
    if event is not None:
        print(event)
    return False        # keep going until the timeout


with connect.mcu_over_probe() as mcu:
    mcu.input_dump(show, timeout=10)
    for kind in ("Press", "Short", "Release"):
        mcu.input_send("Back", kind)
