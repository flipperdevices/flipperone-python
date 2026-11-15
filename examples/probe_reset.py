"""Restart only the MCU through the Debug Probe's reset line, then wait for its CLI."""

from flipperone import connect

with connect.probe_cli() as probe:
    probe.reset("mcu")
with connect.mcu_over_probe(wait_s=10) as mcu:
    print("MCU up for", mcu.uptime(), "s")
