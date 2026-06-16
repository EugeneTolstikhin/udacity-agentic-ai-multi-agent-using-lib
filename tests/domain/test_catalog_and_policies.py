from beavers_choice.domain.catalog import CatalogMatchingService
from beavers_choice.domain.models import ExtractedItem, OrderResult
from beavers_choice.domain.policies import discount_rate, supplier_delivery_date
from beavers_choice.domain.services import ResponseSafetyService


def test_catalog_alias_matching_maps_informal_printer_paper():
    matcher = CatalogMatchingService()

    match = matcher.match_item(
        ExtractedItem(item_description="standard printer paper", quantity=500)
    )

    assert match.item_name == "Standard copy paper"
    assert match.strategy == "alias"


def test_catalog_alias_matching_ignores_quantity_and_unit_wrappers():
    matcher = CatalogMatchingService()

    match = matcher.match_item(
        ExtractedItem(item_description="200 sheets of A4 glossy paper", quantity=200)
    )

    assert match.item_name == "Glossy paper"
    assert match.strategy == "alias"


def test_catalog_rejects_unsupported_items_before_fuzzy_matching():
    matcher = CatalogMatchingService()

    match = matcher.match_item(
        ExtractedItem(item_description="200 balloons", quantity=200)
    )

    assert match.item_name is None
    assert match.strategy == "unmatched"


def test_catalog_fuzzy_threshold_accepts_close_spelling_and_rejects_low_confidence():
    matcher = CatalogMatchingService(threshold=0.82)

    accepted = matcher.match_item(
        ExtractedItem(item_description="glosy paper", quantity=100)
    )
    rejected = matcher.match_item(
        ExtractedItem(item_description="mystery foam sheets", quantity=100)
    )

    assert accepted.item_name == "Glossy paper"
    assert accepted.strategy == "fuzzy"
    assert rejected.item_name is None


def test_discount_and_supplier_delivery_policies_are_deterministic():
    assert discount_rate(499) == 0.0
    assert discount_rate(500) == 0.05
    assert discount_rate(2000) == 0.10
    assert discount_rate(5000) == 0.15
    assert supplier_delivery_date("2025-04-01", 10) == "2025-04-01"
    assert supplier_delivery_date("2025-04-01", 11) == "2025-04-02"
    assert supplier_delivery_date("2025-04-01", 101) == "2025-04-05"
    assert supplier_delivery_date("2025-04-01", 1001) == "2025-04-08"


def test_response_safety_blocks_internal_terms_and_bad_rejection_wording():
    safety = ResponseSafetyService()
    rejected_order = OrderResult(status="rejected", reason="No stock")

    assert not safety.is_safe("The cash balance is 100.")
    assert not safety.rejected_order_is_not_fulfilled(
        rejected_order,
        "Your order is confirmed. Order Reference: BC-1",
    )
    assert "cannot fulfill" in safety.enforce(
        "Your order is confirmed. Order Reference: BC-1",
        "abc",
        rejected_order,
    )


def test_response_safety_rewrites_partial_order_described_as_fully_fulfilled():
    safety = ResponseSafetyService()
    fulfilled_order = OrderResult(
        status="fulfilled",
        order_reference="BC-1",
        charged_total=10.0,
        scheduled_delivery="2025-04-02",
    )

    response = safety.enforce(
        "The order is fully fulfilled. Order Reference: BC-1",
        "abc",
        fulfilled_order,
        ["balloons"],
    )

    assert response.startswith("Your order was partially fulfilled.")
    assert "balloons" in response
