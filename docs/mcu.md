# The MCU's CLI

`Mcu(connect, timeout_s=2, sync_timeout_s=3, settle_s=0.3, reconnect_timeout_s=20)` speaks the MCU's text CLI over a
`Stream`. `connect` is an open stream, or a callable returning a new one; only the latter allows `reconnect()`.

```python
from flipperone import connect

mcu = connect.mcu_over_usb()       # the MCU's own USB port: present while Linux is off
mcu = connect.mcu_over_probe()     # the Debug Probe's MCU port: whatever runs
```

On construction the session is brought to the prompt with Ctrl-C. It is never ended with Ctrl-D or `exit`: on a UART
that stops the CLI until the MCU restarts.

## Commands

| Method | Command | Returns |
|---|---|---|
| `device_info()` | `device_info` | `dict`: `rp2350_firmware_*`, `rp2350_hardware_uid`, ... |
| `uptime()` | `uptime` | seconds |
| `free()` | `free` | `HeapStats` |
| `dmesg()` | `dmesg` | the log as printed |
| `power_info()` | `power info` | `PowerInfo` (mV, mA, %, °C) |
| `power_reboot()`, `power_boot()` | `power reboot`, `power boot` | the session ends; `reconnect()` after a reboot |
| `saradc_get_id()` | `saradc get_id` | the board's hardware ID |
| `nvm_list()`, `nvm_get(kind, key)` | `nvm list`, `nvm get` | keys; a value read as `i`, `u`, `b` or `s` |
| `input_send(key, type)`, `input_dump(handler, timeout)` | `input send`, `input dump` | key and touch events (`KeyEvent`, `TouchEvent`) |
| `led(led, color)` | `led` | `LED_TYPES`, `LED_COLORS` by name or index |
| `help()` | `help` | command names |

Any other command: `run(line)` (a `Result` with `text` and `raw`), `stream(line, seconds)` for one that keeps printing,
`watch(line, handler, timeout)` to follow its lines, `raw_session(line)` to exchange raw bytes (a binary protocol)
with the prompt restored afterwards.

Records are read tolerantly: a field the firmware does not print is `None`, every line is kept in `raw`. Checked with
firmware r175 (13f32b2).

## Errors

`SyncTimeout` (no prompt; `.received` holds what came), `CommandNotFound`, `UsageError` (the command answered with its
usage text), `UnexpectedReply`; all `CliError`.
