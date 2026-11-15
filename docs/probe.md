# The Debug Probe

The Flipper One Debug Probe (`37c1:f131`, USB serial `flip_one_debug`) has four serial ports, by USB interface:

| `Role` | Interface | |
|---|---|---|
| `CPU_CONSOLE` | 2 | the CPU's (Linux's) serial console |
| `MCU_CLI` | 4 | the MCU's CLI over its UART: `connect.mcu_over_probe()` |
| `MCU_LOG` | 6 | the MCU's log |
| `PROBE_CLI` | 8 | the probe's own CLI: `connect.probe_cli()` |

```python
from flipperone.probe import Role, port
port(Role.CPU_CONSOLE).stable_path
```

`Probe` (the probe's CLI): `gpio_get(pin)` for the inputs `INPUT_PINS`, `gpio_set(pin, value)` for the open-drain
reset lines `RESET_PINS` (0 holds the chip in reset), `reset("mcu" | "cpu", hold_s=0.1)` pulses one. Resetting the MCU
restarts only the MCU. Any other command: `run(line)`.
