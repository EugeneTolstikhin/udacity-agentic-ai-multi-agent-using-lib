from beavers_choice.app.workflow import WorkflowOrchestrator
from beavers_choice.domain.catalog import CatalogMatchingService
from beavers_choice.domain.models import ExtractedInquiry, ExtractedItem
from beavers_choice.domain.services import (
    CatalogItemResolver,
    InventoryService,
    OrderFulfillmentService,
    QuoteService,
    ResponseSafetyService,
)
from tests.fakes import (
    DeterministicIds,
    FakePersistence,
    FakePlanner,
    FakeReporter,
    FakeResponder,
    noop_telemetry,
)


def build_workflow(extracted_plan):
    repo = FakePersistence()
    ids = DeterministicIds()
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
        id_generator=ids,
    )
    workflow = WorkflowOrchestrator(
        planner=FakePlanner(extracted_plan),
        specialist_reporter=FakeReporter(),
        responder=FakeResponder(),
        catalog_matcher=matcher,
        inventory_service=inventory,
        quote_service=quote,
        order_service=order,
        response_safety_service=ResponseSafetyService(),
        telemetry=noop_telemetry,
        id_generator=ids,
    )
    return repo, workflow


def test_workflow_runs_with_fake_ports_and_no_llm():
    extracted_plan = ExtractedInquiry(
        route="order",
        request_date="2025-04-01",
        required_by="2025-04-15",
        items=[ExtractedItem(item_description="A4 printer paper", quantity=10)],
        customer_summary="Order A4 printer paper.",
    )
    repo, workflow = build_workflow(extracted_plan)

    result = workflow.handle("Order 10 sheets. Date of request: 2025-04-01")

    assert result.plan.items[0].item_name == "A4 paper"
    assert "Order Reference" in result.response
    assert repo.count_transactions() == 1


def test_workflow_excludes_unsupported_items_and_reports_partial_context():
    extracted_plan = ExtractedInquiry(
        route="order",
        request_date="2025-04-01",
        required_by="2025-04-15",
        items=[
            ExtractedItem(item_description="A4 printer paper", quantity=10),
            ExtractedItem(item_description="balloons", quantity=200),
        ],
        customer_summary="Order paper and balloons.",
    )
    repo, workflow = build_workflow(extracted_plan)

    result = workflow.handle("Order paper and balloons. Date of request: 2025-04-01")

    assert result.plan.unmatched_items == ["balloons"]
    assert result.specialist_results.order is not None
    assert result.specialist_results.order.status == "fulfilled"
    assert repo.count_transactions() == 1

