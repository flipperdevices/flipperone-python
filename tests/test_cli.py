import pytest

from flipperone._cli import CliDevice, check_line, clean
from flipperone.errors import CliError, CommandNotFound, PortNotFound, SyncTimeout
from flipperone.testing import PROMPT, FakeCli

FAST = {"timeout_s": 0.2, "sync_timeout_s": 0.2, "settle_s": 0, "sleep": lambda s: None}


def device(**cli):
    stream = FakeCli(**cli)
    return CliDevice(stream, **FAST), stream


def test_open_brings_the_cli_to_its_prompt():
    _, stream = device()
    assert stream.written == [b"\x03"]


def test_run_returns_the_output_without_echo_and_prompt():
    cli, stream = device(commands={"uptime": "Uptime: 0h1m5s", "free": b"a: 1\r\nb: 2"})
    result = cli.run("uptime")
    assert result.text == "Uptime: 0h1m5s" and result.raw.endswith(PROMPT) and result.command == "uptime"
    assert stream.written[-1] == b"uptime\r" and cli.run("free").lines == ["a: 1", "b: 2"]


def test_unknown_command_and_missing_prompt():
    cli, _ = device(streams={"log": b"1 [I][x] line\r\n"})
    with pytest.raises(CommandNotFound, match="`nope`"):
        cli.run("nope arg")
    with pytest.raises(SyncTimeout, match="prompt after 'log'") as e:
        cli.run("log", timeout=0.05)
    assert b"[I][x] line" in e.value.received


def test_stream_collects_then_stops_with_ctrl_c():
    cli, stream = device(streams={"input dump": b"key: Up type: Press\r\n"}, commands={"uptime": "Uptime: 0h0m1s"})
    assert cli.stream("input dump", 0.02).text == "key: Up type: Press"
    assert stream.written[-1] == b"\x03" and cli.run("uptime").text == "Uptime: 0h0m1s"


def test_watch_lines_and_ticks():
    cli, _ = device(streams={"input dump": b"Press CTRL+C to stop\r\nkey: Up type: Press\r\n"})
    seen: list[str] = []
    assert cli.watch("input dump", lambda line: seen.append(line) or line.startswith("key:"), 1) is True
    assert seen[-1] == "key: Up type: Press"


def test_raw_session_hands_over_bytes_and_restores_the_prompt():
    cli, stream = device(commands={"uptime": "Uptime: 0h0m1s"})
    with cli.raw_session() as raw:
        raw.write(b"\x01\x02")
        assert b"\x01" not in raw.read(0.1)        # non-printable bytes are not echoed by the shell
    assert stream.written[-1] == b"\x03" and cli.run("uptime").text == "Uptime: 0h0m1s"


def test_reconnect_needs_a_way_to_open():
    cli, stream = device()
    cli.close()
    assert stream.closed and not cli.is_open
    with pytest.raises(CliError, match="given a stream"):
        cli.reconnect(0.1)


def test_reconnect_opens_again_and_gives_up_after_its_timeout():
    opened: list[FakeCli] = []
    absent = {"now": False}

    def connect() -> FakeCli:
        if absent["now"]:
            raise PortNotFound("gone")
        opened.append(FakeCli())
        return opened[-1]

    cli = CliDevice(connect, **FAST)
    cli.reconnect()
    assert len(opened) == 2 and opened[0].closed and cli.is_open
    absent["now"] = True
    with pytest.raises(PortNotFound, match="did not come back"):
        cli.reconnect(timeout=0.01)


def test_check_line_and_clean():
    for bad in ("", "é", "a\nb", "x\ty"):
        with pytest.raises(ValueError):
            check_line(bad)
    assert clean(b"power info\r\n\x1b[32mstate : ok\x1b[0m\r\n\r\ncontrol>: ", "power info") == "state : ok"
    assert clean(b"^C\r\ncontrol>: ", None) == "^C"
    assert clean(b"led 4 1\r\n\r\ncontrol>: ", "led 4 1") == ""
