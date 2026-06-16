from __future__ import annotations

from typing import Protocol

from beavers_choice.domain.models import (
    ExtractedInquiry,
    InquiryPlan,
    InventoryResult,
    OrderResult,
    QuoteResult,
    SpecialistReports,
    SpecialistResults,
)


class InquiryPlanner(Protocol):
    """Convert customer text into route, date, quantity, and raw item facts."""

    def plan(self, customer_request: str) -> ExtractedInquiry:
        """Return extracted inquiry facts before deterministic catalog matching."""


class SpecialistReporter(Protocol):
    """Produce specialist textual reports using tool results."""

    def inventory_report(self, plan: InquiryPlan, result: InventoryResult) -> str:
        """Explain inventory result."""

    def quote_report(self, plan: InquiryPlan, result: QuoteResult) -> str:
        """Explain quote result."""

    def order_report(
        self,
        plan: InquiryPlan,
        result: OrderResult,
        reports: SpecialistReports,
    ) -> str:
        """Explain order result."""


class CustomerResponder(Protocol):
    """Produce final customer-facing text from validated facts."""

    def respond(
        self,
        original_request: str,
        plan: InquiryPlan,
        reports: SpecialistReports,
        results: SpecialistResults,
    ) -> str:
        """Return the final customer response."""

