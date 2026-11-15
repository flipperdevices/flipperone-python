from flipperone.linux import Linux, parse_read_many
from flipperone.linux.linux import MARK
from flipperone.testing import FakeShell
from flipperone.transport import CommandResult


def test_read_many_uses_one_command_and_handles_missing_files():
    out = f"{MARK}/a\nline1\nline2\n\n{MARK}/missing:missing\n{MARK}/b\nvalue\n\n"
    t = FakeShell(handler=lambda cmd: out if cmd.startswith("for p in") else None)
    linux = Linux(t)
    result = linux.read_many(["/a", "/missing", "/b"])
    assert result == {"/a": "line1\nline2", "/missing": None, "/b": "value"}
    assert len(t.commands) == 1 and t.commands[0].startswith("for p in /a /missing /b;")
    assert linux.read_many([]) == {} and len(t.commands) == 1


def test_parse_read_many_keeps_empty_files_and_trailing_newlines():
    out = f"{MARK}/empty\n\n{MARK}/nl\nx\n\n\n"
    assert parse_read_many(out, ["/empty", "/nl", "/other"]) == {"/empty": "", "/nl": "x\n", "/other": None}


def test_read_and_sudo_and_glob():
    def answer(cmd):
        if cmd.startswith("sudo -n sh -c "):
            return f"{MARK}/root/only\nsecret\n\n"
        if cmd.startswith("ls -1d"):
            return "/sys/b\n/sys/a\n"
        if cmd.startswith("test -e"):
            return CommandResult(cmd, 1, "", "")
        return None

    t = FakeShell(handler=answer)
    linux = Linux(t, command_timeout_s=3)
    assert linux.read("/root/only", sudo=True) == "secret"
    assert t.commands[0].startswith("sudo -n sh -c 'for p in ")
    assert linux.glob("/sys/*") == ["/sys/a", "/sys/b"]
    assert linux.exists("/nope") is False
    assert linux.run("whatever").code == 127  # no reply configured: the fake says so, the caller decides
