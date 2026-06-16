from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Dict, List, Optional, Protocol

from beavers_choice.domain.models import (
    CatalogItem,
    FinancialReport,
    TransactionRecord,
    TransactionType,
)


class TransactionUnitOfWork(Protocol):
    """Atomic write boundary for stock and sale transactions."""

    def ensure_inventory_item(self, item: CatalogItem, min_stock_level: int = 100) -> None:
        """Ensure a catalog item exists in the inventory reference table."""

    def create_transaction(
        self,
        item_name: str,
        transaction_type: TransactionType,
        quantity: int,
        price: float,
        date: str,
    ) -> int:
        """Create one transaction within the active unit of work."""


class InventoryRepository(Protocol):
    """Read inventory state and reference data."""

    def get_all_inventory(self, as_of_date: str) -> Dict[str, int]:
        """Return positive stock levels as of a date."""

    def get_stock_level(self, item_name: str, as_of_date: str) -> int:
        """Return one item's stock as of a date."""

    def get_minimum_stock_level(self, item_name: str) -> int:
        """Return the configured minimum stock level for an item."""


class TransactionRepository(Protocol):
    """Write and inspect transaction state."""

    def create_transaction(
        self,
        item_name: Optional[str],
        transaction_type: TransactionType,
        quantity: Optional[int],
        price: float,
        date: str,
    ) -> int:
        """Create one transaction."""

    def list_transactions(self, as_of_date: Optional[str] = None) -> List[TransactionRecord]:
        """Return transactions, optionally capped by date."""

    def count_transactions(self, as_of_date: Optional[str] = None) -> int:
        """Return transaction count, optionally capped by date."""

    def transaction(self) -> AbstractContextManager[TransactionUnitOfWork]:
        """Open an atomic transaction unit of work."""


class FinancialReportRepository(Protocol):
    """Read financial state."""

    def get_cash_balance(self, as_of_date: str) -> float:
        """Return cash balance as of a date."""

    def generate_financial_report(self, as_of_date: str) -> FinancialReport:
        """Return cash, inventory value, and total assets as of a date."""


class QuoteHistoryRepository(Protocol):
    """Read historical quote examples."""

    def search_quote_history(self, search_terms: List[str], limit: int = 5) -> List[dict]:
        """Search historical quote records."""

    def initialize(self, seed: int = 137) -> None:
        """Initialize persistence state and reference data."""

