# SPDX-License-Identifier: GPL-3.0-or-later
"""A command's output as a log record: what the ``*.output`` loggers write at DEBUG."""

from __future__ import annotations

DEFAULT_LIMIT = 64 * 1024     # bytes of one stream (stdout or stderr) kept in a record; the rest is only counted
INDENT = "    "


def clip(text: str, limit: int) -> str:
    """``text`` cut to ``limit`` bytes (UTF-8), with how many were left out."""
    data = text.encode()
    if len(data) <= limit:
        return text
    return data[:limit].decode(errors="ignore") + f"\n... {len(data) - limit} B more"


def record(label: str, out: str, err: str = "", limit: int = DEFAULT_LIMIT) -> str | None:
    """``label:`` then the output indented, ``err:`` and stderr after it when there is any; None when both are empty."""
    def indented(text: str) -> str:
        return "\n".join(INDENT + line for line in clip(text, limit).rstrip("\n").split("\n"))
    parts = ([indented(out)] if out else []) + ([INDENT + "err:", indented(err)] if err else [])
    return f"{label}:\n" + "\n".join(parts) if parts else None
