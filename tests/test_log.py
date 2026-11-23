import itertools

from flipperone.mcu.log import LogLine, read_lines
from flipperone.testing import FakeCli


def test_lines_get_this_machines_time_and_lose_their_colours():
    stream = FakeCli(banner=b"12 [I][Flipper] \x1b[32mStartup\x1b[0m complete\r\n13 [E][X] fail\r\n14 incompl")
    ticks = itertools.chain([0.0, 0.1, 0.1], itertools.repeat(5.0))
    lines = list(read_lines(stream, seconds=1, clock=lambda: 1700000000.5, monotonic=lambda: next(ticks)))
    assert lines == [LogLine(1700000000.5, "12 [I][Flipper] Startup complete"), LogLine(1700000000.5, "13 [E][X] fail")]
