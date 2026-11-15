"""Replies of the MCU firmware's CLI, captured from a device (r175, 13f32b2) or written after its format strings."""

DEVICE_INFO = """name                          : Flipper One
rp2350_firmware_commit        : 13f32b2
rp2350_firmware_branch        : dev
rp2350_firmware_commit_dirty  : false
rp2350_firmware_version       : r175
rp2350_firmware_builddate     : 2026-11-12
rp2350_firmware_target        : 2
rp2350_firmware_api_major     : 0
rp2350_firmware_api_minor     : 0
rp2350_firmware_origin_fork   : Official
rp2350_firmware_origin_git    : https://github.com/flipperdevices/flipperone-mcu-firmware.git
rp2350_hardware_uid           : c5976c76a8d0974d"""

FREE = ("Free heap size: 131800\nTotal heap size: 496788\nMinimum heap size: 131264\nMaximum heap block: 129696\n"
        "Pool free: 0\nMaximum pool block: 0")

POWER_INFO = """state                         : charged
BAT.level                     : 96%
BAT.voltage                   : 8580 mV
BAT.current                   : 0 mA
BAT.NTC                       : 29.6C
USB.voltage                   : 8973 mV
USB.current                   : 595 mA
USB.current_limit             : 1600 mA
charger.enabled               : 1
charger.level_limit           : 255%
charger.current_limit         : 3100 mA
charger.temperature           : 45.0C"""

HELP = """Available commands:
\x1b[32mexpander_ext                  input                         uart_echo
power                         saradc                        rpc
help                          exit                          ?
\x1b[0m
Find out more: https://docs.flipper.net/one/development/cli"""

DMESG = "46 [I][SelfCheck] Starting self check autorun\r\n68 [I][Flipper] Startup complete"

COMMANDS = {
    "uptime": "Uptime: 1h32m36s", "free": FREE, "device_info": DEVICE_INFO, "power info": POWER_INFO, "help": HELP,
    "dmesg": DMESG, "nvm list": "LSKV\r\nLedBacklightTime\r\n", "nvm get u LedBacklightTime": "LedBacklightTime: 10000",
    "nvm get s nope": "Key nope is missing", "saradc get_id": "Current SARADC ID: 1",
    "led 4 1": "", "led 16": "", "led": "Usage: led <LED_TYPE> <COLOR>\r\nWhere <LED_TYPE> is:",
    "input send Back Short": "", "input": "Usage: input <command>",
}
