# Transport

Two kinds of transport, both `typing.Protocol`s in `flipperone.transport`:

| | Methods | Implementations |
|---|---|---|
| `Stream` (bytes both ways) | `name`, `read(timeout)`, `write(data)`, `reset_input()`, `close()` | `SerialStream`, `ChannelStream`, `flipperone.testing.FakeCli` |
| `Shell` (commands, files) | `run(command, timeout, on_line)`, `open_stream(command)`, `put`, `get`, `close` | `SshShell`, `SerialShell`, `flipperone.testing.FakeShell` |

Anything with these methods works: wrap a stream to log or mirror it, or bring your own (a TCP bridge, a console).

## Serial ports

`SerialStream(path, baudrate=1500000, dtr=True, busy_timeout_s=0)` opens a port exclusively (`flock`, as terminal
programs do). DTR is raised on open (the Flipper One's CDC ports start a CLI session on it) and lowered on close
(the Debug Probe drives the MCU's UART while it is up). A port another program holds is `PortBusy`; a missing one
`PortNotFound`.

Ports are found by USB serial string and interface number, stable across hosts and re-plugs:

```python
from flipperone.transport import discover, find, wait_for

port = wait_for("flip_one_mcu", timeout=10)        # the MCU's own port, once it appears
port = find(discover(), re.compile(r"f1_debug_[0-9a-f]{4}_"), 4)   # a serial that differs per device: a pattern
port.stable_path                                   # /dev/serial/by-id/... on Linux, /dev/cu.... on macOS
```

The interface number is the CDC data interface (macOS's numbering; Linux's plus one). A pattern must match the whole
serial string. The Debug Probe's ports are easier through `flipperone.probe.port(role)` ([probe.md](probe.md)).

## SSH

`SshShell(SshSettings(host, user="user", password=None, port=22, jump=None))` needs `flipperone[ssh]`; it connects on
first use. Host keys are accepted as they come (a device gets a new one with every install); pass `client_factory`
for another policy. `open_stream(command)` returns the command's stdin/stdout as a `ChannelStream`.

## A serial console

`SerialShell(stream, ready_timeout_s=2)` runs commands on a Linux serial console where a user is logged in (the
CPU's console through the Debug Probe: `connect.cpu_console_over_probe()`); no network needed. `ready()` tells
whether a prompt answers and whether the console prints anything at all. A command runs in a subshell between two
marker lines, its exit code from the closing one. What a console cannot do: separate stderr (it comes with stdout,
`err` stays empty), keep kernel messages out of the output, run anything interactive or spanning lines, copy files
or open a stream (`put`, `get`, `open_stream` raise: use SSH).

## USB devices

`devices(ids)` lists USB devices by `(vid, pid)` (sysfs on Linux, `ioreg` on macOS); `usb_bcd(bus, address)` reads a
device's `bcdUSB`.
