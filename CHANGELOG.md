# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/)
(see [docs/stability.md](docs/stability.md)).

## [Unreleased]

### Added

- DEBUG logging of every action, one line each, never the output: `flipperone.linux` (a command or a file read, its
  exit code, time and sizes; streams, file copies), `flipperone.cli` (an MCU or probe command, its time and reply size;
  streams and watches). `flipperone.wire` (the bytes) stays as it was.

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
