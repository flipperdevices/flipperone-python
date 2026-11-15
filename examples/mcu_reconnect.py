"""Restart the MCU (the whole device powers off and on) and talk to it again."""

from flipperone import connect

mcu = connect.mcu_over_probe()
print("before:", mcu.uptime(), "s")
mcu.power_reboot()
mcu.reconnect(timeout=30)
print("after: ", mcu.uptime(), "s")
mcu.close()
