from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from beavers_choice.domain.catalog import CatalogMatchingService
from beavers_choice.domain.models import (
    CatalogItem,
    ExtractedInquiry,
    FinancialReport,
    InquiryPlan,
    OrderResult,
    SpecialistReports,
    SpecialistResults,
    TransactionRecord,
)
from beavers_choice.domain.services import financial_report_from_values
from beavers_choice.ports.telemetry import NoopTelemetry


class DeterministicIds:
    def __init__(self) -> None:
        self.next_id = 1

    def inquiry_id(self) -> str:
        value = f"inquiry-{self.next_id}"
        self.next_id += 1
        return value

    def order_reference(self, order_date: str) -> str:
        value = f"BC-{order_date.replace('-', '')}-TEST{self.next_id}"
        self.next_id += 1
        return value


class FakeUnitOfWork:
    def __init__(self, repo: "FakePersistence") -> None:
        self.repo = repo
        self.pending: list[TransactionRecord] = []

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is None:
            for record in self.pending:
                self.repo._commit_transaction(record)
        return False

    def ensure_inventory_item(self, item: CatalogItem, min_stock_level: int = 100) -> None:
        self.repo.stock.setdefault(item.item_name, 0)
        self.repo.min_stock.setdefault(item.item_name, min_stock_level)
        self.repo.prices.setdefault(item.item_name, item.unit_price)

    def create_transaction(
        self,
        item_name: str,
        transaction_type: str,
        quantity: int,
        price: float,
        date: str,
    ) -> int:
        record = self.repo._new_record(
            item_name=item_name,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            date=date,
        )
        self.pending.append(record)
        return record.id or 0


class FakePersistence:
    def __init__(self) -> None:
        matcher = CatalogMatchingService()
        self.catalog = {item.item_name: item for item in matcher.catalog_items}
        self.stock: dict[str, int] = {
            "A4 paper": 1000,
            "Cardstock": 20,
            "Glossy paper": 0,
        }
        self.min_stock: dict[str, int] = {
            "A4 paper": 50,
            "Cardstock": 10,
            "Glossy paper": 100,
        }
        self.prices = {
            name: item.unit_price for name, item in self.catalog.items()
        }
        self.transactions: list[TransactionRecord] = []
        self.next_id = 1

    def initialize(self, seed: int = 137) -> None:
        self.transactions.clear()
        self.next_id = 1

    def get_all_inventory(self, as_of_date: str) -> dict[str, int]:
        return {name: stock for name, stock in self.stock.items() if stock > 0}

    def get_stock_level(self, item_name: str, as_of_date: str) -> int:
        return self.stock.get(item_name, 0)

    def get_minimum_stock_level(self, item_name: str) -> int:
        return self.min_stock.get(item_name, 100)

    def get_cash_balance(self, as_of_date: str) -> float:
        sales = sum(
            record.price
            for record in self.transactions
            if record.transaction_type == "sales"
        )
        stock_orders = sum(
            record.price
            for record in self.transactions
            if record.transaction_type == "stock_orders"
        )
        return 50000.0 + sales - stock_orders

    def generate_financial_report(self, as_of_date: str) -> FinancialReport:
        inventory_value = sum(
            quantity * self.prices.get(name, 0.0)
            for name, quantity in self.stock.items()
        )
        return financial_report_from_values(
            as_of_date,
            self.get_cash_balance(as_of_date),
            inventory_value,
        )

    def search_quote_history(self, search_terms: list[str], limit: int = 5) -> list[dict]:
        return [
            {
                "original_request": "Historical A4 paper order",
                "total_amount": 10.0,
                "quote_explanation": "Prior quote example",
                "job_type": "office manager",
                "order_size": "small",
                "event_type": "meeting",
                "order_date": "2025-01-01",
            }
        ][:limit]

    def create_transaction(
        self,
        item_name: Optional[str],
        transaction_type: str,
        quantity: Optional[int],
        price: float,
        date: str,
    ) -> int:
        record = self._new_record(item_name, transaction_type, quantity, price, date)
        self._commit_transaction(record)
        return record.id or 0

    def list_transactions(self, as_of_date: Optional[str] = None) -> list[TransactionRecord]:
        return list(self.transactions)

    def count_transactions(self, as_of_date: Optional[str] = None) -> int:
        return len(self.transactions)

    def transaction(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self)

    def _new_record(
        self,
        item_name: Optional[str],
        transaction_type: str,
        quantity: Optional[int],
        price: float,
        date: str,
    ) -> TransactionRecord:
        record = TransactionRecord(
            id=self.next_id,
            item_name=item_name,
            transaction_type=transaction_type,
            units=quantity,
            price=price,
            transaction_date=date,
        )
        self.next_id += 1
        return record

    def _commit_transaction(self, record: TransactionRecord) -> None:
        self.transactions.append(record)
        if record.item_name and record.units:
            if record.transaction_type == "stock_orders":
                self.stock[record.item_name] = self.stock.get(record.item_name, 0) + record.units
            elif record.transaction_type == "sales":
                self.stock[record.item_name] = self.stock.get(record.item_name, 0) - record.units


class FakePlanner:
    def __init__(self, plan: ExtractedInquiry) -> None:
        self.extracted_plan = plan

    def plan(self, customer_request: str) -> ExtractedInquiry:
        return self.extracted_plan.model_copy(deep=True)


class FakeReporter:
    def inventory_report(self, plan: InquiryPlan, result) -> str:
        return "Inventory checked."

    def quote_report(self, plan: InquiryPlan, result) -> str:
        return "Quote prepared."

    def order_report(self, plan: InquiryPlan, result: OrderResult, reports: SpecialistReports) -> str:
        return f"Order status: {result.status}."


class FakeResponder:
    def respond(
        self,
        original_request: str,
        plan: InquiryPlan,
        reports: SpecialistReports,
        results: SpecialistResults,
    ) -> str:
        if results.order and results.order.status == "fulfilled":
            return (
                f"Order Reference: {results.order.order_reference}. "
                f"Total charged: ${results.order.charged_total:.2f}."
            )
        if results.order and results.order.status == "rejected":
            return f"We cannot fulfill this order: {results.order.reason}"
        return "Your inquiry has been reviewed."


noop_telemetry = NoopTelemetry()
