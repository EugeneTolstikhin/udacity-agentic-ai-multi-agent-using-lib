from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Current time provider."""

    def now(self) -> datetime:
        """Return the current datetime."""

