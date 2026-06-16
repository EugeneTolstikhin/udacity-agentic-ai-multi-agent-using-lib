from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from beavers_choice.domain.models import (
    ExtractedInquiry,
    InquiryPlan,
    InventoryResult,
    OrderResult,
    QuoteResult,
    SpecialistReports,
    SpecialistResults,
)


@dataclass
class ReportDeps:
    """Validated plan and authoritative tool result for a worker report."""

    plan: InquiryPlan
    result: Any
    reports: Optional[SpecialistReports] = None


class PydanticAiAgentAdapter:
    """Pydantic AI implementation of planner, specialist reporter, and responder ports."""

    def __init__(
        self,
        model_name: str,
        base_url: str,
        api_key: str,
        catalog_names: list[str],
    ) -> None:
        self.catalog_names = catalog_names
        self.catalog_prompt = "\n".join(f"- {name}" for name in catalog_names)
        self.agent_model = OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(base_url=base_url, api_key=api_key),
        )

        self.decision_orchestrator_agent = Agent(
            self.agent_model,
            output_type=ExtractedInquiry,
            instructions="""
You are Beaver's Choice decision orchestrator and data validation agent.
Extract route, dates, quantities, and raw customer product phrases. Do not map
products to catalog names yourself; preserve the customer's item wording in
item_description so the deterministic CatalogMatchingService can normalize it.

Routing rules:
- "order": customer asks to buy, place an order, confirm delivery, or supply items.
- "quote": customer asks only for prices, estimates, or quote discussion.
- "inventory": customer asks only about availability or stock.
- "general": no specialist can validly handle the request.

Use the explicit Date of request in the prompt as request_date. Convert delivery
deadlines to YYYY-MM-DD. Never invent quantities or products. Put clearly
unsupported products such as balloons in unmatched_items if you do not include
them as extracted items.
""",
        )

        self.inventory_agent = Agent(
            self.agent_model,
            deps_type=ReportDeps,
            instructions="""
You are Beaver's Choice inventory specialist.
You must call inventory_lookup_tool. Explain current stock, restocking needs,
supplier timing, and deadline feasibility using only the tool result.
""",
        )

        self.quote_agent = Agent(
            self.agent_model,
            deps_type=ReportDeps,
            instructions="""
You are Beaver's Choice quote specialist.
You must call quote_calculation_tool. Present itemized pricing, the bulk
discount, final total, and historical quote context when examples exist.
""",
        )

        self.order_agent = Agent(
            self.agent_model,
            deps_type=ReportDeps,
            instructions="""
You are Beaver's Choice order fulfillment specialist.
You must call order_fulfillment_tool. Only claim confirmation when the tool
status is "fulfilled". Report customer-safe order reference, charged total,
delivery schedule, and rejection reason. Do not reveal transaction IDs,
available cash, inventory valuation, total assets, or restocking costs.
""",
        )

        self.customer_inquiry_agent = Agent(
            self.agent_model,
            instructions="""
You are the customer-facing Beaver's Choice inquiry agent.
Create one concise, professional response from the validated plan, specialist
reports, and authoritative tool results supplied in the prompt. Use only those
facts. Clearly identify unsupported items, prices, discounts, delivery dates,
order status, and next steps. Do not invent stock, products, order references,
deadlines, or guarantees. Never reveal internal cash balances, inventory
valuations, total assets, transaction IDs, restocking costs, or internal errors.
Do not emit placeholder names or signatures. If unsupported items were excluded
and an order was completed, describe the result as partially fulfilled.
""",
        )

        self._register_runtime_instructions()
        self._register_tools()

    def _register_runtime_instructions(self) -> None:
        @self.decision_orchestrator_agent.instructions
        def add_catalog_to_orchestrator() -> str:
            return (
                "Catalog names are listed for context only. Extract raw customer "
                "item wording; do not normalize items yourself.\n"
                f"{self.catalog_prompt}"
            )

        @self.inventory_agent.instructions
        def add_inventory_plan(ctx: RunContext[ReportDeps]) -> str:
            return "Validated inquiry plan:\n" + ctx.deps.plan.model_dump_json(indent=2)

        @self.quote_agent.instructions
        def add_quote_plan(ctx: RunContext[ReportDeps]) -> str:
            return "Validated inquiry plan:\n" + ctx.deps.plan.model_dump_json(indent=2)

        @self.order_agent.instructions
        def add_order_plan(ctx: RunContext[ReportDeps]) -> str:
            return "Validated inquiry plan:\n" + ctx.deps.plan.model_dump_json(indent=2)

    def _register_tools(self) -> None:
        @self.inventory_agent.tool
        def inventory_lookup_tool(ctx: RunContext[ReportDeps]) -> dict:
            """Return the authoritative inventory result for the validated plan."""
            return ctx.deps.result.model_dump()

        @self.quote_agent.tool
        def quote_calculation_tool(ctx: RunContext[ReportDeps]) -> dict:
            """Return the authoritative quote result for the validated plan."""
            return ctx.deps.result.model_dump()

        @self.order_agent.tool
        def order_fulfillment_tool(ctx: RunContext[ReportDeps]) -> dict:
            """Return the authoritative order result for the validated plan."""
            return ctx.deps.result.model_dump()

    def plan(self, customer_request: str) -> ExtractedInquiry:
        return self.decision_orchestrator_agent.run_sync(customer_request).output

    def inventory_report(self, plan: InquiryPlan, result: InventoryResult) -> str:
        deps = ReportDeps(plan=plan, result=result)
        return self.inventory_agent.run_sync(
            "Review this validated inquiry plan using inventory_lookup_tool.",
            deps=deps,
        ).output

    def quote_report(self, plan: InquiryPlan, result: QuoteResult) -> str:
        deps = ReportDeps(plan=plan, result=result)
        return self.quote_agent.run_sync(
            "Prepare pricing for this validated inquiry plan using quote_calculation_tool.",
            deps=deps,
        ).output

    def order_report(
        self,
        plan: InquiryPlan,
        result: OrderResult,
        reports: SpecialistReports,
    ) -> str:
        deps = ReportDeps(plan=plan, result=result, reports=reports)
        return self.order_agent.run_sync(
            "Explain this fulfillment result using order_fulfillment_tool.",
            deps=deps,
        ).output

    def respond(
        self,
        original_request: str,
        plan: InquiryPlan,
        reports: SpecialistReports,
        results: SpecialistResults,
    ) -> str:
        return self.customer_inquiry_agent.run_sync(
            "Original customer inquiry:\n"
            + original_request
            + "\n\nValidated plan:\n"
            + plan.model_dump_json(indent=2)
            + "\n\nSpecialist reports:\n"
            + reports.model_dump_json(indent=2)
            + "\n\nAuthoritative specialist tool results:\n"
            + json.dumps(results.model_dump(mode="json"), indent=2)
        ).output

