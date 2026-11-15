# SPDX-License-Identifier: GPL-3.0-or-later
"""Linux on the Flipper One's main board: :class:`Linux` over any shell (SSH:
:func:`flipperone.connect.linux_over_ssh`)."""

from .linux import Linux, parse_read_many

__all__ = ["Linux", "parse_read_many"]
