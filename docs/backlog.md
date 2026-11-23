# Backlog

Ideas deliberately postponed, each with what it is, why it waits and what would bring it back. Many come from
flipperone-mcu-firmware's agent tools (`scripts/agent_tools`, 2026-11), looked at for what users of this library
could reuse.

## A command-line tool for agents

- **What**: `python -m flipperone` (or a `flipperone` script) over the library: `status`, `screenshot`, `press`,
  `touch`, `log`, `host`, `linux state|start|stop`, `cli`, `probe`. Plain text by default and `--json` with one
  envelope (`{"command": ..., "ok": ..., "data" | "error": ...}`); a tool error (a line `error: ...`, exit 1) kept
  apart from a command's own exit code; `--yes` required for what cuts power or is irreversible
  ([agents.md](agents.md)); a timeout on every command.
- **Why postponed**: the library prints nothing and exits nowhere by design; an agent can call it from Python, and
  the firmware repository has its own tool (`f1.py`).
- **Trigger**: agents outside that repository needing one, or a second tool built on the library.

## SWD through OpenOCD

- **What**: the MCU over the probe's SWD: whether it runs or is halted, the active slot and each slot's header,
  where both cores are (`where`), addresses of a crash report to source lines (`symbol`, needs the build's ELF),
  writing a slot with a check, try-before-you-buy activation, making a slot unbootable. Needs OpenOCD with RP2350
  support (the Pico SDK's) and the board config of `scripts/agent_tools/openocd/flipperone-mcu.cfg`; one SWD client
  at a time (a debugger holding the probe makes every call fail).
- **Why postponed**: a firmware developer's tool; users of the library flash through the USB bootloader
  (`mcu.usbboot`) and read the slots there (`picotool info -a`).
- **Trigger**: a need to read slots or recover the MCU without its USB, in a lab.

## UF2 and picobin codecs

- **What**: pure functions: a UF2 file's sections, blocks and addresses (and whether its payload lies inside a slot);
  a slot's first sector as `erased`, `no image header` or `valid` with its version words and the TBYB flag.
- **Why postponed**: nothing here reads raw flash yet; `picotool` checks files and slots.
- **Trigger**: SWD above, or a check of firmware files before writing them.

## Updating the Debug Probe's firmware

- **What**: `power boot` on the probe's CLI (firmware 0.7.0 and newer) brings it into its bootloader; the `RP2350`
  drive takes a `.uf2`, or `Picotool.load` writes it; then wait for the probe's ports and check `device_info`. Older
  firmware has no software path: the probe's boot button while plugging it in.
- **Why postponed**: a probe is updated rarely and by hand; the probes on the benches are on 0.7.0 now.
- **Trigger**: several probes to keep on one version, or a station that updates its own.
