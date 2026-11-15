# Tests on a device

Read-only tests against a real Flipper One, skipped unless selected and described:

```
FLIPPERONE_MCU=usb|probe            # the MCU's CLI: its own USB port (Linux off) or through the Debug Probe
FLIPPERONE_PROBE=1                  # the Debug Probe's CLI
FLIPPERONE_SSH_HOST=10.0.0.1        # Linux over SSH; FLIPPERONE_SSH_USER (user), FLIPPERONE_SSH_PASSWORD
pytest -m hardware
```
