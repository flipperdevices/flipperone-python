"""Start Linux through the MCU (its default entry), run a command on its console, shut it down (experimental)."""

from flipperone import connect
from flipperone.experimental import host
from flipperone.linux import Linux

with connect.mcu_over_probe() as mcu, connect.cpu_console_over_probe() as console:
    print("before:", host.state(mcu, console))
    print(host.start(mcu, console))
    print(Linux(console).run("uptime").out.strip())
    host.stop(mcu, console)
    print("after:", host.state(mcu, console))
