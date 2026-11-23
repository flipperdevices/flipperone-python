# Experimental

`flipperone.experimental` works on today's firmware and carries no stability promise: it may change or go in any
release. Something proven here moves into the stable API as an addition.

- `screen.screenshot(mcu)` — one frame of the device's screen (`Screen`: `width`, `height`, L8 `pixels`, `png()`),
  over the CLI's RPC session; the few messages needed are encoded by hand.
- `power_screens` — one frame of `power show` / `power consumption` (screens that redraw themselves) and their
  readings (`Reading`: name, value, units).
- `rpc_input` — buttons and the touchpad injected through the same RPC session: `press(mcu, "down", "ok")`,
  `press(mcu, "back", hold_s=0.5, repeats=9)`, `action(mcu, "ok", "release")`, `touch(mcu, x, y, to=(x2, y2))`.
  Firmware before the `SHORT`/`LONG`/`REPEAT` protocol extension (r175) drops those three and logs
  `Unknown action`; `press` and `release` work there.
- `host` — the CPU (Linux) powered by the MCU, watched on the CPU's console: `state(mcu, console)` (a `HostState`),
  `start(mcu, console, entry=None)` (where U-Boot shows its menu, the entry by number or part of its name; a release
  image boots its default by itself; attaches to a Linux already up after an MCU reset),
  `stop(mcu, console, hard=False)`. `console` is `connect.cpu_console_over_probe()`.
