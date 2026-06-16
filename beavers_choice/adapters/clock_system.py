from __future__ import annotations

from datetime import datetime


class SystemClockAdapter:
    """System clock implementation."""

    def now(self) -> datetime:
        return datetime.now()

