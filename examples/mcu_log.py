"""The MCU's log for 10 seconds, each line with this machine's time."""

import time

from flipperone import connect
from flipperone.mcu.log import read_lines

with connect.mcu_log_over_probe() as stream:
    for line in read_lines(stream, seconds=10):
        print(time.strftime("%H:%M:%S", time.localtime(line.time)), line.text)
