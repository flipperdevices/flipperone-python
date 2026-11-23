# Working with a Flipper One from an agent

For an LLM agent (or a script) that drives a device through this library on a machine with a Flipper One and a
Debug Probe attached: what the device does, which calls are safe, and how to work so that nothing is broken and
every claim is checked. The facts were measured on a Flipper One rev. F0B1C2 with MCU firmware r175 and Debug Probe
firmware 0.7.0 (2026-11); many come from flipperone-mcu-firmware's agent tools (`scripts/agent_tools`).

## The device in brief

- **Two processors.** The MCU (RP2350) runs the screen, the keys, the LEDs, the battery and the power; the CPU
  (RK3576) runs Linux (Flipper OS). The MCU powers the CPU while its app `HOST_APP` (`cpu_app_start`) runs.
- **Linux does not start by itself** after the MCU starts or after a shutdown: the MCU has to power the CPU.
  Then a development image waits in U-Boot's menu (on the screen and the console); a release image (bundle 0.1.0)
  boots its default profile by itself and logs `user` in on the console within about 20 s.
  `experimental.host.start()` handles both, `stop()` shuts Linux down.
- **An MCU reset leaves Linux running**: the CPU's rails are held by an I/O expander. The MCU then attaches to the
  running Linux by itself. Its bus is shared with the CPU, so after such a reset I2C errors in the MCU's log
  (`Failed to read reg`, `Failed to initialize Main Expander`, `Bq2579x`) are expected and not a fault of what you
  test; rarely the MCU then cannot control the CPU's power, and it stays on its self-check instead of Linux's screen.
  Then shut Linux down from its console and reset the MCU with the CPU off.
- **USB-C1 belongs to one side at a time**: the MCU's own USB port (`flip_one_mcu`) exists only while the CPU is off.
  Its presence means the CPU is off; its absence means nothing (there may be no cable).
- **One MCU app runs at a time** (`Mcu.desktop_run_app()`); the self-check runs at every start and stays on screen
  when a check failed.
- **Time**: the MCU's log timestamps lose time while it erases flash; use this machine's time
  (`flipperone.mcu.log.LogLine.time`). `dmesg` keeps 10 KB and none of the boot; a crash report survives no reset.
- **Linux**: the CPU's console is logged in as `user` with passwordless `sudo`; `connect.linux_over_probe()` works
  without network, `linux_over_ssh()` needs the USB network (device `10.0.0.1` on a station) and copies files.
- **Ports**: through the probe, `MCU_CLI`, `MCU_LOG`, `CPU_CONSOLE`, `PROBE_CLI` ([probe.md](probe.md)). A port is
  held exclusively: two programs on one port fail with `PortBusy`; different ports work in parallel.

## How much a call may change

| Class | Calls (and MCU commands) | Before calling |
|---|---|---|
| Read-only | `device_info`, `uptime`, `free`, `dmesg`, `power_info`, `saradc_get_id`, `nvm_list`/`nvm_get`, `help`, `input_dump`, `desktop_run_app`/`desktop_list_apps`, `experimental.screen.screenshot`, `experimental.host.state`, `log.read_lines`, `Probe.gpio_get`, `Linux.read`, `Rockusb.mode` | nothing |
| Changes state, recoverable | `led`, `input_send`, `experimental.rpc_input.*` (what a key does depends on the screen), `desktop_start_app`/`desktop_stop_app`, `experimental.host.start`/`stop`, `Probe.reset("mcu")`, `Linux.run` of what you know | check the screen or the state first; read it back after |
| Cuts power or leaves the firmware | `power_reboot` (the whole device off and on), `desktop_stop_app` of `HOST_APP` and `host.stop(hard=True)` (Linux gets no warning: `sync` first), `power_boot` (the MCU's USB bootloader), `desktop_start_app(MASKROM_APP)` | ask the person unless they said the device is free to use |
| Irreversible or switches the device off | `power off`, `power ship` (only the person can switch it on again), `nvm wipe`, `otp ...`, `Picotool.erase_all`/`load`, `i2c write`, `gpio`, `expander_ext` | ask, every time |

## Rules

- **Cheapest signal first.** `uptime`, `desktop_run_app`, `host.state`, the log and console commands are text; a
  screenshot costs an image. Take one when the answer is on the screen and nowhere else: before pressing keys on a
  screen you have not seen, and when the screen itself is what is tested.
- **An unchanged screenshot does not prove a key was ignored**: some actions take seconds to show. Check another
  signal before repeating a press that powers something off, confirms or deletes.
- **Check each step before the next**: read the state back after every action, stop when it is not what you
  expected.
- **Keep the MCU's log read** (`log.read_lines`, saved to a file) while testing something that may crash: the report
  is gone after a reset.
- **What the person sees wins**: when your reading contradicts what they say about the device, they are looking at it.
- **Report what you verified, what you did not, and the state you leave**: Linux up or off, the MCU's app, files
  left on the device.

## What needs the person

A cable to plug or a key the library cannot press (a key held at power-on, the probe's boot button); a device
switched off by `power off`/`power ship`; a probe whose firmware is older than 0.7.0; anything irreversible; a
reading that contradicts what they see.
