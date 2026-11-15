# SPDX-License-Identifier: GPL-3.0-or-later
"""Linux on the Flipper One's main board, over any :class:`~flipperone.transport.base.Shell`."""

from __future__ import annotations

import shlex
from collections.abc import Callable, Iterable
from pathlib import Path

from ..transport.base import CommandResult, Shell, Stream

MARK = "===FLIPPERONE:"    # separates files in a read_many reply; not something sysfs content holds


class Linux:
    """Commands, file reads (sysfs ones batched into one round trip) and file copies on the device's Linux.

    ``shell``: an :class:`~flipperone.transport.ssh.SshShell` (see :func:`flipperone.connect.linux_over_ssh`) or any
    other :class:`~flipperone.transport.base.Shell`. ``command_timeout_s``: the default for :meth:`run`.
    """

    def __init__(self, shell: Shell, *, command_timeout_s: float = 20.0):
        self.shell = shell
        self.command_timeout_s = command_timeout_s

    def run(self, command: str, *, timeout: float | None = None, check: bool = False,
            on_line: Callable[[str], None] | None = None) -> CommandResult:
        """Run a shell command line. ``check``: raise :class:`~flipperone.errors.CommandFailed` on a non-zero exit.
        ``on_line`` gets each line of stdout as it arrives; the result still holds all of it."""
        result = self.shell.run(command, self.command_timeout_s if timeout is None else timeout, on_line)
        return result.check() if check else result

    def sudo(self, command: str, *, timeout: float | None = None, check: bool = False,
             on_line: Callable[[str], None] | None = None) -> CommandResult:
        """:meth:`run` as root through ``sudo -n`` (the user needs passwordless sudo)."""
        return self.run(f"sudo -n sh -c {shlex.quote(command)}", timeout=timeout, check=check, on_line=on_line)

    def open_stream(self, command: str, *, sudo: bool = False) -> Stream:
        """A command as a duplex byte stream (its stdin and stdout); closing the stream ends it."""
        if sudo:
            command = f"sudo -n sh -c {shlex.quote(command)}"
        return self.shell.open_stream(command)

    def read(self, path: str, *, sudo: bool = False) -> str | None:
        """A file's content, or ``None`` when it does not exist or cannot be read."""
        return self.read_many([path], sudo=sudo)[path]

    def read_many(self, paths: Iterable[str], *, sudo: bool = False) -> dict[str, str | None]:
        """Several files in one command (every command costs a round trip); missing or unreadable ones are ``None``."""
        paths = list(paths)
        if not paths:
            return {}
        script = ("for p in " + " ".join(shlex.quote(p) for p in paths)
                  + f"; do if [ -r \"$p\" ]; then printf '%s\\n' '{MARK}'\"$p\"; cat -- \"$p\" 2>/dev/null; "
                  f"printf '\\n'; else printf '%s\\n' '{MARK}'\"$p\"':missing'; fi; done")
        result = self.sudo(script) if sudo else self.run(script)
        return parse_read_many(result.out, paths)

    def glob(self, pattern: str) -> list[str]:
        """Paths matching a shell pattern, sorted; empty when nothing matches."""
        result = self.run(f"ls -1d {pattern} 2>/dev/null")
        return sorted(line for line in result.out.splitlines() if line.strip())

    def exists(self, path: str) -> bool:
        return self.run(f"test -e {shlex.quote(path)}").ok

    def put(self, local: Path, remote: str) -> None:
        self.shell.put(local, remote)

    def get(self, remote: str, local: Path) -> None:
        self.shell.get(remote, local)

    def close(self) -> None:
        self.shell.close()

    def __enter__(self) -> Linux:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def parse_read_many(out: str, paths: Iterable[str]) -> dict[str, str | None]:
    """The reply of :meth:`Linux.read_many`'s script, per path."""
    result: dict[str, str | None] = dict.fromkeys(paths)
    current: str | None = None
    chunks: dict[str, list[str]] = {}
    lines = out.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for line in lines:
        if line.startswith(MARK):
            name = line[len(MARK):]
            if name.endswith(":missing") and name[:-len(":missing")] in result:
                current = None
                continue
            current = name
            chunks[name] = []
        elif current is not None:
            chunks[current].append(line)
    for name, body in chunks.items():
        text = "\n".join(body)
        result[name] = text[:-1] if text.endswith("\n") else text
    return result
