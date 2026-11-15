"""Commands and sysfs reads on Linux over SSH: ``python linux_run.py 10.0.0.1 PASSWORD``."""

import sys

from flipperone import connect

host, password = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None
with connect.linux_over_ssh(host, password=password) as linux:
    print(linux.run("uname -a", check=True).out.strip())
    files = linux.read_many(["/proc/device-tree/model", "/etc/hostname"])
    for path, text in files.items():
        print(f"{path}: {(text or '').strip()}")
