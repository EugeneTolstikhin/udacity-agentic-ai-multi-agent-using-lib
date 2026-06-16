from __future__ import annotations

import re

from beavers_choice.domain.catalog import CatalogMatchingService
from beavers_choice.domain.models import (
    ExtractedInquiry,
    SpecialistReports,
    SpecialistResults,
    WorkflowResult,
)
from beavers_choice.domain.policies import parse_date
from beavers_choice.domain.services import (
    InventoryService,
    OrderFulfillmentService,
    QuoteService,
    ResponseSafetyService,
)
from beavers_choice.ports.ai import CustomerResponder, InquiryPlanner, SpecialistReporter
from beavers_choice.ports.ids import IdGeneratorPort
from beavers_choice.ports.telemetry import TelemetryPort


class WorkflowOrchestrator:
    """Application workflow that coordinates ports and domain services."""

    def __init__(
        self,
        planner: InquiryPlanner,
        specialist_reporter: SpecialistReporter,
        responder: CustomerResponder,
        catalog_matcher: CatalogMatchingService,
        inventory_service: InventoryService,
        quote_service: QuoteService,
        order_service: OrderFulfillmentService,
        response_safety_service: ResponseSafetyService,
        telemetry: TelemetryPort,
        id_generator: IdGeneratorPort,
    ) -> None:
        self.planner = planner
        self.specialist_reporter = specialist_reporter
        self.responder = responder
        self.catalog_matcher = catalog_matcher
        self.inventory_service = inventory_service
        self.quote_service = quote_service
        self.order_service = order_service
        self.response_safety_service = response_safety_service
        self.telemetry = telemetry
        self.id_generator = id_generator

    def handle(self, customer_request: str) -> WorkflowResult:
        inquiry_id = self.id_generator.inquiry_id()
        with self.telemetry.span(
            "Process customer inquiry",
            inquiry_id=inquiry_id,
            customer_request=customer_request,
        ):
            try:
                extracted_plan = self.planner.plan(customer_request)
                explicit_request_date = re.search(
                    r"Date of request:\s*(\d{4}-\d{2}-\d{2})",
                    customer_request,
                    flags=re.IGNORECASE,
                )
                if explicit_request_date:
                    extracted_plan.request_date = explicit_request_date.group(1)

                parse_date(extracted_plan.request_date, "request_date")
                if extracted_plan.required_by:
                    parse_date(extracted_plan.required_by, "required_by")

                plan = self.catalog_matcher.normalize_plan(extracted_plan)
                self.telemetry.info(
                    "Inquiry validated and routed",
                    inquiry_id=inquiry_id,
                    route=plan.route,
                    request_date=plan.request_date,
                    required_by=plan.required_by,
                    item_count=len(plan.items),
                    unmatched_items=plan.unmatched_items,
                )

                reports = SpecialistReports()
                results = SpecialistResults()

                if plan.items and plan.route in {"inventory", "quote", "order"}:
                    inventory_result = self.inventory_service.inspect_inventory(
                        plan.items,
                        plan.request_date,
                        plan.required_by,
                    )
                    results.inventory = inventory_result
                    reports.inventory = self.specialist_reporter.inventory_report(
                        plan,
                        inventory_result,
                    )

                if plan.items and plan.route in {"quote", "order"}:
                    quote_result = self.quote_service.prepare_quote(
                        plan.items,
                        plan.request_date,
                    )
                    results.quote = quote_result
                    reports.quote = self.specialist_reporter.quote_report(
                        plan,
                        quote_result,
                    )

                if plan.items and plan.route == "order":
                    order_result = self.order_service.fulfill_order(
                        plan.items,
                        plan.request_date,
                        plan.required_by,
                    )
                    results.order = order_result
                    reports.order = self.specialist_reporter.order_report(
                        plan,
                        order_result,
                        reports,
                    )

                response = self.responder.respond(
                    customer_request,
                    plan,
                    reports,
                    results,
                )
                response = self.response_safety_service.enforce(
                    response,
                    inquiry_id,
                    results.order,
                    plan.unmatched_items,
                )
                self.telemetry.info(
                    "Inquiry completed",
                    inquiry_id=inquiry_id,
                    route=plan.route,
                    specialist_agents=[
                        name
                        for name, value in reports.model_dump().items()
                        if value
                    ],
                )
                return WorkflowResult(
                    inquiry_id=inquiry_id,
                    plan=plan,
                    specialist_reports=reports,
                    specialist_results=results,
                    response=response,
                )
            except Exception as exc:
                self.telemetry.exception(
                    "Inquiry workflow failed",
                    inquiry_id=inquiry_id,
                    error_type=type(exc).__name__,
                )
                response = self.response_safety_service.safe_fallback(inquiry_id)
                return WorkflowResult(
                    inquiry_id=inquiry_id,
                    plan=self.catalog_matcher.normalize_plan(
                        ExtractedInquiry(
                            route="general",
                            request_date="2025-01-01",
                            customer_summary="Workflow failed before validation.",
                        )
                    ),
                    specialist_reports=SpecialistReports(),
                    specialist_results=SpecialistResults(),
                    response=response,
                )

    def response_for(self, customer_request: str) -> str:
        return self.handle(customer_request).response
