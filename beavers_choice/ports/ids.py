from __future__ import annotations

from typing import Protocol


class IdGeneratorPort(Protocol):
    """ID generation boundary."""

    def inquiry_id(self) -> str:
        """Return a unique inquiry ID."""

    def order_reference(self, order_date: str) -> str:
        """Return a customer-safe order reference."""

