# Experimental

`flipperone.experimental` works on today's firmware and carries no stability promise: it may change or go in any
release. Something proven here moves into the stable API as an addition.

- `screen.screenshot(mcu)` — one frame of the device's screen (`Screen`: `width`, `height`, L8 `pixels`, `png()`),
  over the CLI's RPC session; the few messages needed are encoded by hand.
- `power_screens` — one frame of `power show` / `power consumption` (screens that redraw themselves) and their
  readings (`Reading`: name, value, units).
