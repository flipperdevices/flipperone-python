# SPDX-License-Identifier: GPL-3.0-or-later
import logging

from flipperone._output import clip, record
from flipperone.linux import Linux
from flipperone.testing import FakeShell


def test_record_indents_stdout_then_stderr_and_clips():
    assert record("uname -r", "7.4.0\n") == "uname -r:\n    7.4.0"
    assert record("x", "a\nb", "oops") == "x:\n    a\n    b\n    err:\n    oops"
    assert record("x", "", "") is None
    assert clip("abcdef", 4) == "abcd\n... 2 B more"


def test_linux_logs_the_action_and_its_output(caplog):
    shell = FakeShell({"uname -r": "7.4.0\n"})
    with caplog.at_level(logging.DEBUG, logger="flipperone"):
        Linux(shell, log_output_limit=3).run("uname -r")
    lines = [(r.name, r.getMessage()) for r in caplog.records]
    assert lines[0][0] == "flipperone.linux" and lines[0][1].startswith("uname -r -> exit 0, ")
    assert lines[1] == ("flipperone.linux.output", "uname -r:\n    7.4\n    ... 3 B more")
