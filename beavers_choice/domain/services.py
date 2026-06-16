from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from beavers_choice.domain.catalog import CatalogMatchingService
from beavers_choice.domain.errors import UnknownCatalogItemError
from beavers_choice.domain.models import (
    CatalogItem,
    FinancialReport,
    InventoryLine,
    InventoryResult,
    OrderResult,
    QuoteLine,
    QuoteResult,
    RequestedItem,
)
from beavers_choice.domain.policies import (
    discount_rate,
    is_deliverable_by_deadline,
    parse_date,
    supplier_delivery_date,
)
from beavers_choice.ports.ids import IdGeneratorPort
from beavers_choice.ports.repositories import (
    FinancialReportRepository,
    InventoryRepository,
    QuoteHistoryRepository,
    TransactionRepository,
)


class CatalogItemResolver:
    """Combine duplicate requested catalog items and attach catalog metadata."""

    def __init__(self, matcher: CatalogMatchingService) -> None:
        self.matcher = matcher

    def resolve(self, items: Iterable[RequestedItem]) -> list[dict[str, Any]]:
        by_name = self.matcher.catalog_by_name()
        combined: Dict[str, Dict[str, Any]] = {}

        for requested_item in items:
            catalog_item = by_name.get(requested_item.item_name.strip().casefold())
            if catalog_item is None:
                raise UnknownCatalogItemError(
                    f"Unknown catalog item {requested_item.item_name!r}."
                )

            exact_name = catalog_item.item_name
            if exact_name not in combined:
                combined[exact_name] = {
                    "catalog_item": catalog_item,
                    "item_name": exact_name,
                    "category": catalog_item.category,
                    "unit_price": catalog_item.unit_price,
                    "quantity": 0,
                    "requested_descriptions": [],
                }

            combined[exact_name]["quantity"] += requested_item.quantity
            if requested_item.requested_description:
                combined[exact_name]["requested_descriptions"].append(
                    requested_item.requested_description
                )

        return list(combined.values())


class InventoryService:
    """Inventory availability, safety stock, and supplier-timing rules."""

    def __init__(
        self,
        inventory_repository: InventoryRepository,
        resolver: CatalogItemResolver,
    ) -> None:
        self.inventory_repository = inventory_repository
        self.resolver = resolver

    def inspect_inventory(
        self,
        items: List[RequestedItem],
        as_of_date: str,
        required_by: Optional[str] = None,
    ) -> InventoryResult:
        request_date = parse_date(as_of_date, "as_of_date")
        deadline = parse_date(required_by, "required_by") if required_by else None
        complete_inventory = self.inventory_repository.get_all_inventory(as_of_date)
        lines: list[InventoryLine] = []

        for item in self.resolver.resolve(items):
            current_stock = self.inventory_repository.get_stock_level(
                item["item_name"],
                as_of_date,
            )
            snapshot_stock = int(complete_inventory.get(item["item_name"], 0))
            minimum_stock = self.inventory_repository.get_minimum_stock_level(
                item["item_name"]
            )
            restock_quantity = max(
                0,
                item["quantity"] + minimum_stock - current_stock,
            )
            supplier_delivery = (
                supplier_delivery_date(as_of_date, restock_quantity)
                if restock_quantity
                else request_date.strftime("%Y-%m-%d")
            )

            lines.append(
                InventoryLine(
                    item_name=item["item_name"],
                    requested_quantity=item["quantity"],
                    current_stock=current_stock,
                    snapshot_stock=snapshot_stock,
                    minimum_stock_level=minimum_stock,
                    available_without_restock=current_stock >= item["quantity"],
                    restock_quantity=restock_quantity,
                    supplier_delivery_date=supplier_delivery,
                    deliverable_by_deadline=is_deliverable_by_deadline(
                        supplier_delivery,
                        deadline.strftime("%Y-%m-%d") if deadline else None,
                    ),
                )
            )

        return InventoryResult(
            as_of_date=request_date.strftime("%Y-%m-%d"),
            required_by=deadline.strftime("%Y-%m-%d") if deadline else None,
            inventory_items_in_stock=len(complete_inventory),
            all_items_deliverable=all(line.deliverable_by_deadline for line in lines),
            items=lines,
        )


class QuoteService:
    """Pricing, discount, and historical quote context rules."""

    def __init__(
        self,
        quote_history_repository: QuoteHistoryRepository,
        resolver: CatalogItemResolver,
    ) -> None:
        self.quote_history_repository = quote_history_repository
        self.resolver = resolver

    def prepare_quote(
        self,
        items: List[RequestedItem],
        request_date: str,
    ) -> QuoteResult:
        parse_date(request_date, "request_date")
        catalog_items = self.resolver.resolve(items)
        total_quantity = sum(item["quantity"] for item in catalog_items)
        applied_discount_rate = discount_rate(total_quantity)

        lines: list[QuoteLine] = []
        base_total = 0.0
        for item in catalog_items:
            subtotal = round(item["quantity"] * item["unit_price"], 2)
            discounted_subtotal = round(subtotal * (1 - applied_discount_rate), 2)
            base_total += subtotal
            lines.append(
                QuoteLine(
                    item_name=item["item_name"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    subtotal=subtotal,
                    discounted_subtotal=discounted_subtotal,
                )
            )

        total = round(base_total * (1 - applied_discount_rate), 2)
        if lines:
            rounding_difference = round(
                total - sum(line.discounted_subtotal for line in lines),
                2,
            )
            lines[-1].discounted_subtotal = round(
                lines[-1].discounted_subtotal + rounding_difference,
                2,
            )

        return QuoteResult(
            request_date=request_date,
            total_quantity=total_quantity,
            base_total=round(base_total, 2),
            discount_rate=applied_discount_rate,
            discount_amount=round(base_total - total, 2),
            total=total,
            lines=lines,
            historical_examples=self._historical_quote_examples(
                [item["item_name"] for item in catalog_items]
            ),
        )

    def _historical_quote_examples(
        self,
        item_names: List[str],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        examples: List[Dict[str, Any]] = []
        seen = set()

        for item_name in item_names:
            search_candidates = [item_name]
            meaningful_words = [
                word
                for word in re.findall(r"[A-Za-z]+", item_name)
                if len(word) >= 4
            ]
            if meaningful_words:
                search_candidates.append(meaningful_words[0])

            for search_term in search_candidates:
                matches = self.quote_history_repository.search_quote_history(
                    [search_term],
                    limit=2,
                )
                for match in matches:
                    key = (
                        match.get("original_request"),
                        match.get("total_amount"),
                    )
                    if key not in seen:
                        seen.add(key)
                        examples.append(match)
                    if len(examples) >= limit:
                        return examples

        return examples


class OrderFulfillmentService:
    """Validate, restock, and record customer orders."""

    def __init__(
        self,
        inventory_service: InventoryService,
        quote_service: QuoteService,
        transaction_repository: TransactionRepository,
        financial_report_repository: FinancialReportRepository,
        resolver: CatalogItemResolver,
        id_generator: IdGeneratorPort,
    ) -> None:
        self.inventory_service = inventory_service
        self.quote_service = quote_service
        self.transaction_repository = transaction_repository
        self.financial_report_repository = financial_report_repository
        self.resolver = resolver
        self.id_generator = id_generator

    def fulfill_order(
        self,
        items: List[RequestedItem],
        order_date: str,
        required_by: Optional[str] = None,
    ) -> OrderResult:
        inventory = self.inventory_service.inspect_inventory(
            items,
            order_date,
            required_by,
        )
        blocked_items = [
            line.item_name
            for line in inventory.items
            if not line.deliverable_by_deadline
        ]
        if blocked_items:
            return OrderResult(
                status="rejected",
                reason="Supplier lead time exceeds the requested delivery date.",
                blocked_items=blocked_items,
                inventory=inventory,
            )

        quote = self.quote_service.prepare_quote(items, order_date)
        catalog_items = {
            item["item_name"]: item for item in self.resolver.resolve(items)
        }
        restock_cost = round(
            sum(
                line.restock_quantity
                * catalog_items[line.item_name]["unit_price"]
                for line in inventory.items
            ),
            2,
        )
        available_cash = self.financial_report_repository.get_cash_balance(order_date)
        if restock_cost > available_cash:
            return OrderResult(
                status="rejected",
                reason="Insufficient cash to purchase the required restock.",
                required_cash=restock_cost,
                available_cash=round(available_cash, 2),
                inventory=inventory,
            )

        transaction_ids = {"stock_orders": [], "sales": []}
        with self.transaction_repository.transaction() as unit_of_work:
            for item in catalog_items.values():
                unit_of_work.ensure_inventory_item(
                    item["catalog_item"],
                    min_stock_level=100,
                )

            for inventory_line in inventory.items:
                restock_quantity = inventory_line.restock_quantity
                if restock_quantity:
                    unit_price = catalog_items[inventory_line.item_name]["unit_price"]
                    transaction_id = unit_of_work.create_transaction(
                        item_name=inventory_line.item_name,
                        transaction_type="stock_orders",
                        quantity=restock_quantity,
                        price=round(restock_quantity * unit_price, 2),
                        date=order_date,
                    )
                    transaction_ids["stock_orders"].append(transaction_id)

            for quote_line in quote.lines:
                transaction_id = unit_of_work.create_transaction(
                    item_name=quote_line.item_name,
                    transaction_type="sales",
                    quantity=quote_line.quantity,
                    price=quote_line.discounted_subtotal,
                    date=order_date,
                )
                transaction_ids["sales"].append(transaction_id)

        delivery_dates = [
            line.supplier_delivery_date
            for line in inventory.items
        ]
        scheduled_delivery = max(delivery_dates) if delivery_dates else order_date
        financial_report = self.financial_report_repository.generate_financial_report(
            order_date
        )

        return OrderResult(
            status="fulfilled",
            order_reference=self.id_generator.order_reference(order_date),
            order_date=order_date,
            scheduled_delivery=scheduled_delivery,
            required_by=required_by,
            charged_total=quote.total,
            discount_rate=quote.discount_rate,
            restock_cost=restock_cost,
            transaction_ids=transaction_ids,
            post_order_financial_state={
                "cash_balance": round(float(financial_report.cash_balance), 2),
                "inventory_value": round(float(financial_report.inventory_value), 2),
                "total_assets": round(float(financial_report.total_assets), 2),
            },
            items=quote.lines,
            inventory=inventory,
        )


class ResponseSafetyService:
    """Validate customer-facing response text."""

    SENSITIVE_PATTERNS = (
        r"transaction[_\s-]?id",
        r"cash balance",
        r"inventory value",
        r"total assets",
        r"restock(?:ing)? cost",
        r"traceback",
        r"runtimeerror",
        r"sqlalchemy",
        r"logfire",
    )

    PLACEHOLDER_PATTERNS = (
        r"\[your name\]",
        r"\[customer",
        r"\[manufacturer",
        r"\[contact",
    )

    def is_safe(self, response: str) -> bool:
        lower_response = response.casefold()
        return not any(
            re.search(pattern, lower_response, flags=re.IGNORECASE)
            for pattern in (*self.SENSITIVE_PATTERNS, *self.PLACEHOLDER_PATTERNS)
        )

    def rejected_order_is_not_fulfilled(
        self,
        order_result: OrderResult,
        response: str,
    ) -> bool:
        if order_result.status != "rejected":
            return True
        lower_response = response.casefold()
        fulfilled_terms = (
            "successfully fulfilled",
            "order has been fulfilled",
            "order is confirmed",
            "order reference",
        )
        return not any(term in lower_response for term in fulfilled_terms)

    def partial_order_is_not_fully_fulfilled(
        self,
        order_result: OrderResult,
        response: str,
        unmatched_items: Optional[List[str]] = None,
    ) -> bool:
        if (
            order_result.status != "fulfilled"
            or not unmatched_items
        ):
            return True
        lower_response = response.casefold()
        fully_fulfilled_terms = (
            "fully fulfilled",
            "all items are",
            "all requested items",
            "complete order",
        )
        return not any(term in lower_response for term in fully_fulfilled_terms)

    def partial_fulfillment_fallback(
        self,
        order_result: OrderResult,
        unmatched_items: List[str],
    ) -> str:
        unmatched_text = ", ".join(unmatched_items)
        parts = [
            "Your order was partially fulfilled.",
        ]
        if order_result.order_reference:
            parts.append(f"Order Reference: {order_result.order_reference}.")
        if order_result.charged_total is not None:
            parts.append(f"Total charged: ${order_result.charged_total:.2f}.")
        if order_result.scheduled_delivery:
            parts.append(
                f"Scheduled delivery: {order_result.scheduled_delivery}."
            )
        parts.append(
            "Unsupported or unmatched items were excluded: "
            f"{unmatched_text}."
        )
        return " ".join(parts)

    def safe_fallback(self, inquiry_id: str) -> str:
        return (
            "We could not complete this inquiry at this time. "
            f"Please contact support and provide reference {inquiry_id}."
        )

    def enforce(
        self,
        response: str,
        inquiry_id: str,
        order_result: Optional[OrderResult] = None,
        unmatched_items: Optional[List[str]] = None,
    ) -> str:
        if not self.is_safe(response):
            return self.safe_fallback(inquiry_id)
        if order_result and not self.rejected_order_is_not_fulfilled(
            order_result,
            response,
        ):
            return (
                "We reviewed your request but cannot fulfill the order as requested. "
                "The available inventory and supplier delivery timing do not meet "
                "the required conditions."
            )
        if (
            order_result
            and unmatched_items
            and not self.partial_order_is_not_fully_fulfilled(
                order_result,
                response,
                unmatched_items,
            )
        ):
            return self.partial_fulfillment_fallback(order_result, unmatched_items)
        return response


def financial_report_from_values(
    as_of_date: str,
    cash_balance: float,
    inventory_value: float,
) -> FinancialReport:
    return FinancialReport(
        as_of_date=as_of_date,
        cash_balance=round(float(cash_balance), 2),
        inventory_value=round(float(inventory_value), 2),
        total_assets=round(float(cash_balance + inventory_value), 2),
    )
