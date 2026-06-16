from beavers_choice.domain.catalog import CatalogMatchingService
from beavers_choice.domain.models import RequestedItem
from beavers_choice.domain.services import (
    CatalogItemResolver,
    InventoryService,
    OrderFulfillmentService,
    QuoteService,
)
from tests.fakes import DeterministicIds, FakePersistence


def build_services():
    repo = FakePersistence()
    matcher = CatalogMatchingService()
    resolver = CatalogItemResolver(matcher)
    inventory = InventoryService(repo, resolver)
    quote = QuoteService(repo, resolver)
    order = OrderFulfillmentService(
        inventory_service=inventory,
        quote_service=quote,
        transaction_repository=repo,
        financial_report_repository=repo,
        resolver=resolver,
        id_generator=DeterministicIds(),
    )
    return repo, inventory, quote, order


def test_fulfilled_order_creates_expected_sale_transaction_once():
    repo, _, _, order = build_services()

    result = order.fulfill_order(
        [RequestedItem(item_name="A4 paper", quantity=10)],
        "2025-04-01",
        "2025-04-15",
    )

    assert result.status == "fulfilled"
    assert repo.count_transactions() == 1
    assert repo.transactions[0].transaction_type == "sales"
    assert repo.transactions[0].item_name == "A4 paper"
    assert repo.stock["A4 paper"] == 990


def test_restock_transaction_is_created_only_when_needed():
    repo, _, _, order = build_services()

    result = order.fulfill_order(
        [RequestedItem(item_name="Cardstock", quantity=15)],
        "2025-04-01",
        "2025-04-15",
    )

    assert result.status == "fulfilled"
    assert [record.transaction_type for record in repo.transactions] == [
        "stock_orders",
        "sales",
    ]
    assert repo.transactions[0].units == 5
    assert repo.stock["Cardstock"] == 10


def test_rejected_order_does_not_mutate_transactions_or_stock():
    repo, _, _, order = build_services()
    before_stock = dict(repo.stock)

    result = order.fulfill_order(
        [RequestedItem(item_name="Glossy paper", quantity=2000)],
        "2025-04-01",
        "2025-04-01",
    )

    assert result.status == "rejected"
    assert repo.count_transactions() == 0
    assert repo.stock == before_stock


def test_quote_service_applies_bulk_discount_and_history():
    _, _, quote, _ = build_services()

    result = quote.prepare_quote(
        [RequestedItem(item_name="A4 paper", quantity=5000)],
        "2025-04-01",
    )

    assert result.discount_rate == 0.15
    assert result.total == 212.5
    assert result.historical_examples

