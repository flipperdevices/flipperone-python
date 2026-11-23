# SPDX-License-Identifier: GPL-3.0-or-later
"""Text helpers shared by the CLIs and the consoles (internal)."""

from __future__ import annotations

import re

ANSI_CSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """``text`` without ANSI escape sequences (colours, cursor moves)."""
    return ANSI_CSI.sub("", text)
