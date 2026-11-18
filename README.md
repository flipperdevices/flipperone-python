# flipperone

Work with a [Flipper One](https://docs.flipper.net/one) from Python: the MCU's command-line interface, Linux on the
main board over SSH, the Debug Probe, and the MCU's and the CPU's USB bootloaders.

```
pip install flipperone            # serial: the MCU and the Debug Probe
pip install 'flipperone[ssh]'     # and Linux over SSH
```

Python 3.12+, Linux and macOS.

```python
from flipperone import connect

with connect.mcu_over_probe() as mcu:                       # or mcu_over_usb() while Linux is off
    print(mcu.device_info()["rp2350_firmware_version"], mcu.power_info().battery_level)

with connect.linux_over_ssh("10.0.0.1", password="...") as linux:
    print(linux.run("uname -r").out)
```

The subsystem classes take any transport: `Mcu(stream)` runs over a serial port, an SSH channel or your own stream;
`Linux(shell)` over SSH or your own shell. `flipperone.connect` only pairs them the usual way.

Nothing is printed. At DEBUG the library logs every action in one line, never its output: `flipperone.linux`
(commands, file reads, streams, copies: exit code, time, sizes) and `flipperone.cli` (MCU and probe commands: time,
reply size). `flipperone.wire` logs the bytes themselves at DEBUG: silence it on its own when only the actions are
wanted (`logging.getLogger("flipperone.wire").setLevel(logging.WARNING)`).

## Documentation

- [docs/transport.md](docs/transport.md) — streams, shells, finding ports
- [docs/mcu.md](docs/mcu.md) — the MCU's CLI
- [docs/linux.md](docs/linux.md) — Linux on the main board
- [docs/probe.md](docs/probe.md) — the Debug Probe
- [docs/bootloaders.md](docs/bootloaders.md) — the MCU's USB bootloader (`picotool`), MaskROM (`rockusb`)
- [docs/experimental.md](docs/experimental.md) — what carries no stability promise
- [docs/stability.md](docs/stability.md) — versions and what may change
- [examples/](examples/) — short scripts

## Development

```
uv venv && uv pip install -e '.[ssh]' --group dev
uvx nox                      # tests on 3.12-3.14, ruff, mypy --strict
pytest -m hardware           # on a device: tests/hardware/README.md
```

Rules for contributors and coding agents: [AGENTS.md](AGENTS.md).

## License

GPL-3.0-or-later: [LICENSE](LICENSE).
