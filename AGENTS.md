# Rules for contributors and coding agents

- **A reference.** This library is the company's statement of the right way to work with a Flipper One from
  Python. Only established, documented ways belong here. Workarounds, test logic, limits, expected values and
  project settings belong to the projects that use it.
- **Extend, do not change.** Projects depend on it: after 1.0 nothing public is changed or removed without a
  deprecation (see [docs/stability.md](docs/stability.md)). Prefer a new function or argument with a default over
  a changed behaviour. Every change goes into [CHANGELOG.md](CHANGELOG.md).
- **No architecture imposed.** Subsystem classes take any transport; nothing reads files, prints or exits; settings
  are arguments with defaults; logs go through `logging`.
- **Minimal dependencies**: `pyserial`; `paramiko` only as the `ssh` extra. A new dependency needs a strong reason.
- **New CLI wrappers** only for user-level commands with a settled format; parse tolerantly (unknown lines into
  `raw`, missing fields `None`). Anything else goes to `flipperone.experimental` first.
- **Tests**: every public function has a unit test without a device (`flipperone.testing` fakes, captured output);
  `uvx nox` passes on Python 3.12-3.14 with `ruff` and `mypy --strict`. Tests on a device are read-only and marked
  `hardware`.
- **Docs**: a docstring on every public object; the page in `docs/` updated; an example when a new way of use
  appears. Keep both short.
- Files carry `# SPDX-License-Identifier: GPL-3.0-or-later`.
