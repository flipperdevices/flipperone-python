# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/)
(see [docs/stability.md](docs/stability.md)).

## [Unreleased]

### Changed

- `flipperone.probe` finds the Debug Probe by its firmware 0.7.0 serial string, `f1_debug_xxxx_` (one per probe);
  a probe with older firmware (`flip_one_debug`) is no longer found. `USB_SERIAL` is now a compiled pattern.
- `Mcu.sync()`: when Ctrl-C brings no prompt, an RPC session left open is closed in that protocol and Ctrl-C tried
  once more (a healthy session sees only Ctrl-C, as before).

### Added

- `flipperone.probe.probes()`, `select()`, `ProbeId`: the attached probes and the choice of one; `port()`,
  `wait_port()` and the `connect.*_over_probe()` functions take `probe=` (its serial's four digits or its chip ID);
  several probes and none named: `AmbiguousDevice`.
- `transport.find()` / `wait_for()` / `connect.serial_opener()` take a compiled pattern for a serial string
  (`transport.Serial`).
- `transport.SerialShell`: a `Shell` over a Linux serial console; `connect.cpu_console_over_probe()`,
  `connect.linux_over_probe()`: Linux through the Debug Probe without network.
- `flipperone.mcu.log` (`read_lines`, `LogLine`): the MCU's log with this machine's time;
  `connect.mcu_log_over_probe()`.
- `Mcu.desktop_run_app()`, `desktop_list_apps()`, `desktop_start_app()`, `desktop_stop_app()`; `HOST_APP`,
  `MASKROM_APP`.
- `flipperone.experimental.rpc_input`: keys (click, hold with repeats, raw events) and touch (tap, swipe) over RPC.
- `flipperone.experimental.host`: the CPU's power through the MCU (`state`, `start` with U-Boot's menu entry and
  attaching to a running Linux, `stop` clean or hard).
- `docs/agents.md` (working with a device from an agent), `docs/backlog.md`.

- DEBUG logging of every action, one line each, never the output: `flipperone.linux` (a command or a file read, its
  exit code, time and sizes; streams, file copies), `flipperone.cli` (an MCU or probe command, its time and reply size;
  streams and watches). `flipperone.wire` (the bytes) stays as it was.
- DEBUG logging of each command's output, as a record after its line, indented, stderr under `err:`:
  `flipperone.linux.output`, `flipperone.cli.output`; `log_output_limit` of `Linux` and of the CLI devices (64 KiB by
  default) caps each stream, the rest is counted.

## [0.1.0] - 2026-11-15

### Added

- `flipperone.transport`: `Stream` and `Shell`; `SerialStream`, `ChannelStream`, `SshShell` (`[ssh]`); USB serial
  ports by serial string and interface; USB devices and `bcdUSB`.
- `flipperone.mcu`: `Mcu` (the MCU's CLI: `run`, `stream`, `watch`, `raw_session`, `reconnect` and the user-level
  commands), its USB port, `usbboot` (`picotool`).
- `flipperone.linux`: `Linux` (commands, batched file reads, streams, file copies).
- `flipperone.probe`: the Debug Probe's ports by role and its CLI (`gpio`, `reset`).
- `flipperone.maskrom`: `Rockusb` (list, mode, `download-boot`).
- `flipperone.connect`: `mcu_over_usb`, `mcu_over_probe`, `probe_cli`, `linux_over_ssh`.
- `flipperone.testing`: `FakeShell`, `FakeCli`.
- `flipperone.experimental`: the RPC screenshot, the live `power` screens.
