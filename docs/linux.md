# Linux on the main board

`Linux(shell, command_timeout_s=20)` over any `Shell`; over SSH: `connect.linux_over_ssh(host, user="user",
password=None, port=22, jump=None)` (needs `flipperone[ssh]`); over the CPU's serial console through the Debug Probe,
without network: `connect.linux_over_probe()` (commands and file reads only, see
[transport.md](transport.md#a-serial-console)).

| Method | |
|---|---|
| `run(command, timeout=None, check=False, on_line=None)` | a `CommandResult` (`code`, `out`, `err`); `check` raises `CommandFailed` |
| `sudo(...)` | the same through `sudo -n` (passwordless sudo) |
| `read(path, sudo=False)` | a file's content or `None` |
| `read_many(paths, sudo=False)` | several files in one command (sysfs reads in one round trip) |
| `glob(pattern)`, `exists(path)` | |
| `open_stream(command, sudo=False)` | the command's stdin/stdout as a `Stream` |
| `put(local, remote)`, `get(remote, local)` | file copies |
