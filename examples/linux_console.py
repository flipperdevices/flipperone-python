"""Linux on the device over the CPU's serial console through the Debug Probe: no network needed."""

from flipperone import connect

with connect.linux_over_probe() as linux:
    print(linux.run("uname -r").out.strip(), "|", linux.read("/etc/hostname"))
