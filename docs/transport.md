# Transport

Two kinds of transport, both `typing.Protocol`s in `flipperone.transport`:

| | Methods | Implementations |
|---|---|---|
| `Stream` (bytes both ways) | `name`, `read(timeout)`, `write(data)`, `reset_input()`, `close()` | `SerialStream`, `ChannelStream`, `flipperone.testing.FakeCli` |
| `Shell` (commands, files) | `run(command, timeout, on_line)`, `open_stream(command)`, `put`, `get`, `close` | `SshShell`, `flipperone.testing.FakeShell` |

Anything with these methods works: wrap a stream to log or mirror it, or bring your own (a TCP bridge, a console).

## Serial ports

`SerialStream(path, baudrate=1500000, dtr=True, busy_timeout_s=0)` opens a port exclusively (`flock`, as terminal
programs do). DTR is raised on open (the Flipper One's CDC ports start a CLI session on it) and lowered on close
(the Debug Probe drives the MCU's UART while it is up). A port another program holds is `PortBusy`; a missing one
`PortNotFound`.

Ports are found by USB serial string and interface number, stable across hosts and re-plugs:

```python
from flipperone.transport import discover, find, wait_for

port = find(discover(), "flip_one_debug", 4)       # the Debug Probe's MCU port
port = wait_for("flip_one_mcu", timeout=10)        # the MCU's own port, once it appears
port.stable_path                                   # /dev/serial/by-id/... on Linux, /dev/cu.... on macOS
```

The interface number is the CDC data interface (macOS's numbering; Linux's plus one).

## SSH

`SshShell(SshSettings(host, user="user", password=None, port=22, jump=None))` needs `flipperone[ssh]`; it connects on
first use. Host keys are accepted as they come (a device gets a new one with every install); pass `client_factory`
for another policy. `open_stream(command)` returns the command's stdin/stdout as a `ChannelStream`.

## USB devices

`devices(ids)` lists USB devices by `(vid, pid)` (sysfs on Linux, `ioreg` on macOS); `usb_bcd(bus, address)` reads a
device's `bcdUSB`.
