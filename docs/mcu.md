# The MCU's CLI

`Mcu(connect, timeout_s=2, sync_timeout_s=3, settle_s=0.3, reconnect_timeout_s=20)` speaks the MCU's text CLI over a
`Stream`. `connect` is an open stream, or a callable returning a new one; only the latter allows `reconnect()`.

```python
from flipperone import connect

mcu = connect.mcu_over_usb()       # the MCU's own USB port: present while Linux is off
mcu = connect.mcu_over_probe()     # the Debug Probe's MCU port: whatever runs
```

On construction the session is brought to the prompt with Ctrl-C. It is never ended with Ctrl-D or `exit`: on a UART
that stops the CLI until the MCU restarts. When Ctrl-C brings no prompt, the session may have been left inside the
RPC protocol (a program stopped in the middle of `rpc`): it is closed in that protocol and Ctrl-C tried once more.

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
| `desktop_run_app()` | `desktop get_run_app` | the id of the app on screen, `None` on the desktop |
| `desktop_list_apps()` | `desktop list_apps` | app id -> name |
| `desktop_start_app(app)`, `desktop_stop_app()` | `desktop start_app`, `desktop stop_app` | the id started or stopped; a refusal raises `CliError` with the firmware's reason |
| `help()` | `help` | command names |

Any other command: `run(line)` (a `Result` with `text` and `raw`), `stream(line, seconds)` for one that keeps printing,
`watch(line, handler, timeout)` to follow its lines, `raw_session(line)` to exchange raw bytes (a binary protocol)
with the prompt restored afterwards.

Records are read tolerantly: a field the firmware does not print is `None`, every line is kept in `raw`. Checked with
firmware r175 (13f32b2).

One MCU app runs at a time; the desktop is not an app. `HOST_APP` (`cpu_app_start`) powers the CPU and shows its
screen: stopping it cuts the CPU's power without warning Linux. `MASKROM_APP` (`cpu_app_maskrom`) powers the CPU
held in its boot ROM. The self-check (`self_check`) runs at every start and stays on screen when a check failed;
The CPU's power through these apps, watched on its console: `flipperone.experimental.host`.

## The log

`flipperone.mcu.log.read_lines(stream, seconds=None)` gives the log line by line (`LogLine`: `time` on this
machine's clock, `text`), from the Debug Probe's log port (`connect.mcu_log_over_probe()`). The MCU's own
timestamps lose time while it erases flash; `dmesg` keeps only the last 10 KB and nothing of the boot; a crash report
does not survive a reset. Keep the log read while testing something that may crash.

## Errors

`SyncTimeout` (no prompt; `.received` holds what came), `CommandNotFound`, `UsageError` (the command answered with its
usage text), `UnexpectedReply`; all `CliError`.
