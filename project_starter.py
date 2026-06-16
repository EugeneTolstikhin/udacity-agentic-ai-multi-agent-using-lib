"""Compatibility entrypoint for the Beaver's Choice hexagonal application.

The real implementation lives in the beavers_choice package. This file keeps
the reviewer-facing starter helper names and Docker command stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from sqlalchemy import Engine
from sqlalchemy.engine import Connection

from beavers_choice.adapters.ids_uuid import UuidGeneratorAdapter
from beavers_choice.adapters.output_csv import print_results_validation_summary
from beavers_choice.adapters.persistence_sqlalchemy import (
    SqlAlchemyPersistenceAdapter,
    generate_sample_inventory,
)
from beavers_choice.app.container import AppContainer
from beavers_choice.domain.catalog import PAPER_SUPPLIES, CatalogMatchingService
from beavers_choice.domain.models import ExtractedItem, InquiryPlan, RequestedItem
from beavers_choice.domain.policies import supplier_delivery_date
from beavers_choice.domain.services import (
    CatalogItemResolver,
    InventoryService,
    OrderFulfillmentService,
    QuoteService,
)


paper_supplies = [item.model_dump() for item in PAPER_SUPPLIES]


@dataclass
class _ServiceBundle:
    persistence: SqlAlchemyPersistenceAdapter
    matcher: CatalogMatchingService
    resolver: CatalogItemResolver
    inventory: InventoryService
    quote: QuoteService
    order: OrderFulfillmentService


@lru_cache(maxsize=1)
def _persistence() -> SqlAlchemyPersistenceAdapter:
    return SqlAlchemyPersistenceAdapter()


@lru_cache(maxsize=1)
def _service_bundle() -> _ServiceBundle:
    persistence = _persistence()
    matcher = CatalogMatchingService()
    resolver = CatalogItemResolver(matcher)
    inventory = InventoryService(persistence, resolver)
    quote = QuoteService(persistence, resolver)
    order = OrderFulfillmentService(
        inventory_service=inventory,
        quote_service=quote,
        transaction_repository=persistence,
        financial_report_repository=persistence,
        resolver=resolver,
        id_generator=UuidGeneratorAdapter(),
    )
    return _ServiceBundle(
        persistence=persistence,
        matcher=matcher,
        resolver=resolver,
        inventory=inventory,
        quote=quote,
        order=order,
    )


@lru_cache(maxsize=1)
def _container() -> AppContainer:
    return AppContainer.production()


db_engine = _persistence().engine


def init_database(db_engine: Optional[Engine] = None, seed: int = 137) -> Engine:
    """Initialize the Beaver's Choice database."""
    adapter = (
        SqlAlchemyPersistenceAdapter(engine=db_engine)
        if db_engine is not None
        else _persistence()
    )
    adapter.initialize(seed=seed)
    return adapter.engine


def create_transaction(
    item_name: Optional[str],
    transaction_type: str,
    quantity: Optional[int],
    price: float,
    date: Union[str, datetime],
    connection: Optional[Connection] = None,
) -> int:
    """Create one stock order or sales transaction."""
    return _persistence().create_transaction(
        item_name=item_name,
        transaction_type=transaction_type,  # type: ignore[arg-type]
        quantity=quantity,
        price=price,
        date=date,
        connection=connection,
    )


def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """Return positive stock levels as of a date."""
    return _persistence().get_all_inventory(as_of_date)


def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """Return the starter-compatible stock-level DataFrame."""
    return _persistence().get_stock_level_frame(item_name, as_of_date)


def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """Estimate supplier delivery date from Beaver's Choice lead-time policy."""
    return supplier_delivery_date(input_date_str, quantity)


def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """Return cash balance as of a date."""
    return _persistence().get_cash_balance(as_of_date)


def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """Return the starter-compatible financial report dictionary."""
    return _persistence().generate_financial_report_dict(as_of_date)


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """Search historical quotes."""
    return _persistence().search_quote_history(search_terms, limit)


def inspect_inventory(
    items: List[RequestedItem],
    as_of_date: str,
    required_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Check stock, safety-stock restocking needs, and deadline feasibility."""
    return _service_bundle().inventory.inspect_inventory(
        items,
        as_of_date,
        required_by,
    ).model_dump()


def prepare_quote(
    items: List[RequestedItem],
    request_date: str,
) -> Dict[str, Any]:
    """Create an itemized quote and retrieve relevant quote history."""
    return _service_bundle().quote.prepare_quote(items, request_date).model_dump()


def fulfill_order(
    items: List[RequestedItem],
    order_date: str,
    required_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate, restock, and record an order."""
    return _service_bundle().order.fulfill_order(
        items,
        order_date,
        required_by,
    ).model_dump()


def call_multi_agent_system(customer_request: str) -> str:
    """Validate, route, execute specialist agents, and synthesize one response."""
    return _container().workflow.response_for(customer_request)


def run_test_scenarios():
    """Run the complete 20-scenario evaluation."""
    return [row.model_dump() for row in _container().evaluation.run()]


def main() -> None:
    run_test_scenarios()


if __name__ == "__main__":
    main()
