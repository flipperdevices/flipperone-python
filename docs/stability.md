# Stability

Versions follow SemVer. Before 1.0 the API may still change between minor versions; every change is in the
changelog. From 1.0:

- the public API (everything not starting with `_` outside `flipperone.experimental`) only grows;
- something to be removed is deprecated first (a `DeprecationWarning` and a changelog entry) and removed no earlier
  than the next major version;
- `flipperone.experimental` may change in any release.

Parsers of the MCU's CLI follow the firmware: a field the firmware stops printing becomes `None` rather than an
error; a changed format of a stable command is a bug to fix in a patch release.
