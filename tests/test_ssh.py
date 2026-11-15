
from typing import ClassVar

import pytest

from flipperone.errors import CommandFailed, ConnectError
from flipperone.testing import FakeShell
from flipperone.transport import CommandResult, SshSettings, SshShell
from flipperone.transport.ssh import parse_jump


def test_parse_jump():
    assert parse_jump("user@bastion") == ("user", "bastion", 22)
    assert parse_jump("u@h:2200") == ("u", "h", 2200)
    with pytest.raises(ConnectError):
        parse_jump("bastion")


def test_command_result_check():
    ok = CommandResult("true", 0, "", "")
    assert ok.ok and ok.check() is ok
    with pytest.raises(CommandFailed, match="'false' exited with 1: boom"):
        CommandResult("false", 1, "", "boom\n").check()


class FakeClient:
    """Enough of paramiko.SSHClient for the transport: records connect arguments, answers exec_command."""

    instances: ClassVar[list["FakeClient"]] = []

    def __init__(self):
        self.connect_args = None
        self.closed = False
        FakeClient.instances.append(self)

    def connect(self, host, **kwargs):
        self.connect_args = (host, kwargs)
        if host == "unreachable":
            raise OSError("no route")

    def get_transport(self):
        class T:
            @staticmethod
            def open_channel(kind, dest, src):
                return ("channel", kind, dest)
        return T()

    def exec_command(self, command, timeout=None):
        class Stream:
            def __init__(self, data, code=0):
                self.data, self.channel = data, type("C", (), {"recv_exit_status": staticmethod(lambda: code)})()

            def read(self):
                return self.data

        return None, Stream(f"ran {command}".encode(), 3), Stream(b"")

    def close(self):
        self.closed = True


def test_ssh_shell_connects_through_a_jump_host_and_runs_commands():
    FakeClient.instances.clear()
    t = SshShell(SshSettings(host="dut", user="u", password="p", jump="j@bastion:2200"), client_factory=FakeClient)
    result = t.run("uptime", timeout=5)
    assert result == CommandResult("uptime", 3, "ran uptime", "", result.duration_s)
    jump, dut = FakeClient.instances
    assert jump.connect_args == ("bastion", {"port": 2200, "username": "j", "timeout": 10.0})
    assert dut.connect_args[0] == "dut" and dut.connect_args[1]["sock"] == ("channel", "direct-tcpip", ("dut", 22))
    assert dut.connect_args[1]["password"] == "p"
    t.close()
    assert jump.closed and dut.closed


def test_ssh_shell_reports_unreachable_hosts():
    FakeClient.instances.clear()
    with pytest.raises(ConnectError, match="cannot reach u@unreachable:22"):
        SshShell(SshSettings(host="unreachable", user="u"), client_factory=FakeClient).connect()


def test_fake_shell(tmp_path):
    t = FakeShell(replies={"uptime": "1 2", "fail": CommandResult("fail", 2, "", "no"),
                               "dyn": lambda cmd: f"got {cmd}"})
    assert t.run("uptime", 1).out == "1 2" and t.run("fail", 1).code == 2 and t.run("dyn", 1).out == "got dyn"
    assert t.run("nope", 1).code == 127 and t.commands == ["uptime", "fail", "dyn", "nope"]
    local = tmp_path / "f.txt"
    local.write_text("hello")
    t.put(local, "/tmp/f.txt")
    t.get("/tmp/f.txt", tmp_path / "out" / "g.txt")
    assert (tmp_path / "out" / "g.txt").read_text() == "hello"
    t.close()
    assert t.closed
