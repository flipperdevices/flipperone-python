# SPDX-License-Identifier: GPL-3.0-or-later
"""A :class:`~flipperone.transport.base.Shell` over SSH (paramiko: ``pip install flipperone[ssh]``)."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import CommandTimeout, ConnectError
from .base import CommandResult
from .channel import ChannelStream


@dataclass(frozen=True)
class SshSettings:
    """Where and how to connect. ``password=None``: keys and the agent only. ``jump``: ``user@host[:port]`` of a
    host the connection is tunnelled through."""

    host: str
    user: str = "user"
    password: str | None = None
    port: int = 22
    jump: str | None = None
    connect_timeout_s: float = 10.0

    def describe(self) -> str:
        via = f" via {self.jump}" if self.jump else ""
        return f"{self.user}@{self.host}:{self.port}{via}"


def parse_jump(spec: str) -> tuple[str, str, int]:
    """``user@host[:port]`` -> (user, host, port)."""
    user, sep, rest = spec.rpartition("@")
    if not sep:
        raise ConnectError(f"jump host must be user@host[:port], not {spec!r}")
    host, _, port = rest.partition(":")
    return user, host, int(port) if port else 22


class SshShell:
    """SSH to Linux on the device. Connects on first use. Host keys are accepted as they come (a device gets a new
    one with every install); pass ``client_factory`` for another policy."""

    def __init__(self, settings: SshSettings, client_factory: Callable[[], Any] | None = None):
        self.settings = settings
        self._factory = client_factory or _paramiko_client
        self._client: Any = None
        self._jump_client: Any = None
        self._sftp: Any = None

    def connect(self) -> None:
        """Open the session now (otherwise the first command does)."""
        s = self.settings
        sock = None
        try:
            if s.jump:
                juser, jhost, jport = parse_jump(s.jump)
                self._jump_client = self._factory()
                self._jump_client.connect(jhost, port=jport, username=juser, timeout=s.connect_timeout_s)
                sock = self._jump_client.get_transport().open_channel("direct-tcpip", (s.host, s.port), ("", 0))
            self._client = self._factory()
            self._client.connect(s.host, port=s.port, username=s.user, password=s.password,
                                 timeout=s.connect_timeout_s, sock=sock, allow_agent=True, look_for_keys=True)
        except OSError as e:
            raise ConnectError(f"cannot reach {s.describe()}: {e}") from None
        except Exception as e:  # paramiko's own exception tree
            raise ConnectError(f"cannot connect to {s.describe()}: {e}") from None

    def run(self, command: str, timeout: float, on_line: Callable[[str], None] | None = None) -> CommandResult:
        client = self._require()
        started = time.monotonic()
        try:
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            if on_line is None:
                out = stdout.read().decode("utf-8", errors="replace")
            else:
                lines = []
                for raw in iter(stdout.readline, ""):
                    line = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
                    lines.append(line)
                    on_line(line.rstrip("\n"))
                out = "".join(lines)
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
        except TimeoutError:
            raise CommandTimeout(f"'{command}' produced nothing for {timeout:g} s") from None
        return CommandResult(command, code, out, err, time.monotonic() - started)

    def open_stream(self, command: str) -> ChannelStream:
        channel = self._require().get_transport().open_session()
        channel.exec_command(command)
        return ChannelStream(channel, f"{self.settings.host}:{command[:40]}")

    def put(self, local: Path, remote: str) -> None:
        self._sftp_client().put(str(local), remote)

    def get(self, remote: str, local: Path) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        self._sftp_client().get(remote, str(local))

    def close(self) -> None:
        for c in (self._sftp, self._client, self._jump_client):
            if c is not None:
                with contextlib.suppress(Exception):
                    c.close()
        self._sftp = self._client = self._jump_client = None

    def __enter__(self) -> SshShell:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _require(self) -> Any:
        if self._client is None:
            self.connect()
        return self._client

    def _sftp_client(self) -> Any:
        if self._sftp is None:
            self._sftp = self._require().open_sftp()
        return self._sftp


def _paramiko_client() -> Any:
    try:
        import paramiko
    except ImportError:
        raise ConnectError("SSH needs paramiko: pip install 'flipperone[ssh]'") from None
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client
