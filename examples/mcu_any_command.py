"""Any CLI command, and one that keeps printing (the MCU's log for 3 seconds)."""

from flipperone import connect

with connect.mcu_over_probe() as mcu:
    print(mcu.run("uptime").text)
    print(mcu.stream("log", seconds=3).text)
