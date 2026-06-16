from __future__ import annotations

import uuid


class UuidGeneratorAdapter:
    """UUID-backed ID generator."""

    def inquiry_id(self) -> str:
        return uuid.uuid4().hex

    def order_reference(self, order_date: str) -> str:
        return f"BC-{order_date.replace('-', '')}-{uuid.uuid4().hex[:8].upper()}"

