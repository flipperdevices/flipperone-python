"""Battery, USB input and charger as the MCU reads them."""

from flipperone import connect

with connect.mcu_over_probe() as mcu:
    p = mcu.power_info()
    print(f"{p.state}: battery {p.battery_level} % {p.battery_voltage_mv} mV, USB {p.usb_voltage_mv} mV")
