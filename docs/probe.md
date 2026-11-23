# The Debug Probe

The Flipper One Debug Probe (`37c1:f131`) with firmware 0.7.0 or newer: each probe has its own USB serial string,
`f1_debug_xxxx_` (four hex digits folded from its chip ID; the full chip ID ends the USB product string). A probe with
older firmware (serial `flip_one_debug`) is not found: update it from
<https://github.com/flipperdevices/flipperone-debug-probe> (hold `MCU RESET & PROBE BOOT` while plugging it in, then
`picotool load -v -x FILE.uf2`; from 0.7.0 on, its CLI's `power boot` enters the bootloader).

Four serial ports, by USB interface, all at 1500000 baud whatever the host asks for:

| `Role` | Interface | |
|---|---|---|
| `CPU_CONSOLE` | 2 | the CPU's (Linux's) serial console: `connect.cpu_console_over_probe()`, `connect.linux_over_probe()` |
| `MCU_CLI` | 4 | the MCU's CLI over its UART: `connect.mcu_over_probe()` |
| `MCU_LOG` | 6 | the MCU's log, output only: `connect.mcu_log_over_probe()` |
| `PROBE_CLI` | 8 | the probe's own CLI: `connect.probe_cli()` |

```python
from flipperone.probe import Role, port, probes
probes()                                  # [ProbeId(serial='f1_debug_4b30_', chip_id='D7DA0C50B04820F2')]
port(Role.CPU_CONSOLE).stable_path
port(Role.MCU_CLI, probe="4b30")          # one of several: its serial's four digits, or its chip ID (or a prefix)
```

With one probe attached nothing needs naming; with several, `port()` and every `connect.*_over_probe(probe=...)`
raise `AmbiguousDevice` until one is named. A probe sits between this machine and one device: if cables may have
moved, check the device behind it (`Mcu.device_info()["rp2350_hardware_uid"]`).

`Probe` (the probe's CLI): `gpio_get(pin)` for the inputs `INPUT_PINS`, `gpio_set(pin, value)` for the open-drain
reset lines `RESET_PINS` (0 holds the chip in reset), `reset("mcu" | "cpu", hold_s=0.1)` pulses one. Resetting the MCU
restarts only the MCU, and works while a debugger holds the probe's SWD. Linux keeps running through it (see
[agents.md](agents.md)). Any other command: `run(line)` (`device_info`, `power reboot`, `power boot`, `help`).
