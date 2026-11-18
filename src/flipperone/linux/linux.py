# SPDX-License-Identifier: GPL-3.0-or-later
"""Linux on the Flipper One's main board, over any :class:`~flipperone.transport.base.Shell`."""

from __future__ import annotations

import logging
import shlex
from collections.abc import Callable, Iterable
from pathlib import Path

from .._output import DEFAULT_LIMIT
from .._output import record as output_record
from ..transport.base import CommandResult, Shell, Stream

log = logging.getLogger("flipperone.linux")    # DEBUG: one line per action (what, exit code, time, sizes), no output
output_log = logging.getLogger("flipperone.linux.output")   # DEBUG: each command's stdout and stderr, after its line

MARK = "===FLIPPERONE:"    # separates files in a read_many reply; not something sysfs content holds


class Linux:
    """Commands, file reads (sysfs ones batched into one round trip) and file copies on the device's Linux.

    ``shell``: an :class:`~flipperone.transport.ssh.SshShell` (see :func:`flipperone.connect.linux_over_ssh`) or any
    other :class:`~flipperone.transport.base.Shell`. ``command_timeout_s``: the default for :meth:`run`.
    ``log_output_limit``: bytes of a command's stdout (and of its stderr) the ``flipperone.linux.output`` logger keeps.
    """

    def __init__(self, shell: Shell, *, command_timeout_s: float = 20.0, log_output_limit: int = DEFAULT_LIMIT):
        self.shell = shell
        self.command_timeout_s = command_timeout_s
        self.log_output_limit = log_output_limit

    def run(self, command: str, *, timeout: float | None = None, check: bool = False,
            on_line: Callable[[str], None] | None = None) -> CommandResult:
        """Run a shell command line. ``check``: raise :class:`~flipperone.errors.CommandFailed` on a non-zero exit.
        ``on_line`` gets each line of stdout as it arrives; the result still holds all of it."""
        return self._run(command, command, timeout, check, on_line)

    def sudo(self, command: str, *, timeout: float | None = None, check: bool = False,
             on_line: Callable[[str], None] | None = None) -> CommandResult:
        """:meth:`run` as root through ``sudo -n`` (the user needs passwordless sudo)."""
        return self._run(f"sudo -n sh -c {shlex.quote(command)}", f"sudo {command}", timeout, check, on_line)

    def _run(self, command: str, label: str, timeout: float | None, check: bool,
             on_line: Callable[[str], None] | None) -> CommandResult:
        """``command`` run, logged as ``label`` (what the caller asked for, not the wrapping)."""
        try:
            result = self.shell.run(command, self.command_timeout_s if timeout is None else timeout, on_line)
        except Exception as e:
            log.debug("%s -> %s: %s", label, type(e).__name__, e)
            raise
        log.debug("%s -> exit %d, %.2f s, out %d B%s", label, result.code, result.duration_s, len(result.out),
                  f", err {len(result.err)} B" if result.err else "")
        if output_log.isEnabledFor(logging.DEBUG):
            text = output_record(label, result.out, result.err, self.log_output_limit)
            if text:
                output_log.debug("%s", text)
        return result.check() if check else result

    def open_stream(self, command: str, *, sudo: bool = False) -> Stream:
        """A command as a duplex byte stream (its stdin and stdout); closing the stream ends it."""
        log.debug("stream %s%s", "sudo " if sudo else "", command)
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
        label = f"{'sudo ' if sudo else ''}read {' '.join(paths)}"
        command = f"sudo -n sh -c {shlex.quote(script)}" if sudo else script
        result = self._run(command, label, None, False, None)
        return parse_read_many(result.out, paths)

    def glob(self, pattern: str) -> list[str]:
        """Paths matching a shell pattern, sorted; empty when nothing matches."""
        result = self.run(f"ls -1d {pattern} 2>/dev/null")
        return sorted(line for line in result.out.splitlines() if line.strip())

    def exists(self, path: str) -> bool:
        return self.run(f"test -e {shlex.quote(path)}").ok

    def put(self, local: Path, remote: str) -> None:
        log.debug("put %s -> %s (%d B)", local, remote, local.stat().st_size)
        self.shell.put(local, remote)

    def get(self, remote: str, local: Path) -> None:
        self.shell.get(remote, local)
        log.debug("get %s -> %s (%d B)", remote, local, local.stat().st_size)

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
