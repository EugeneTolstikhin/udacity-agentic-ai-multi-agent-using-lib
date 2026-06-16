from __future__ import annotations

from dataclasses import dataclass

from beavers_choice.adapters.ai_pydantic import PydanticAiAgentAdapter
from beavers_choice.adapters.clock_system import SystemClockAdapter
from beavers_choice.adapters.ids_uuid import UuidGeneratorAdapter
from beavers_choice.adapters.output_csv import CsvEvaluationOutputAdapter
from beavers_choice.adapters.persistence_sqlalchemy import SqlAlchemyPersistenceAdapter
from beavers_choice.adapters.telemetry_logfire import LogfireTelemetryAdapter
from beavers_choice.app.config import AppConfig
from beavers_choice.app.evaluation import EvaluationRunner
from beavers_choice.app.workflow import WorkflowOrchestrator
from beavers_choice.domain.catalog import CatalogMatchingService
from beavers_choice.domain.services import (
    CatalogItemResolver,
    InventoryService,
    OrderFulfillmentService,
    QuoteService,
    ResponseSafetyService,
)


@dataclass
class AppContainer:
    """Production app wiring for strict ports-and-adapters architecture."""

    config: AppConfig
    persistence: SqlAlchemyPersistenceAdapter
    telemetry: LogfireTelemetryAdapter
    ids: UuidGeneratorAdapter
    clock: SystemClockAdapter
    catalog_matcher: CatalogMatchingService
    resolver: CatalogItemResolver
    inventory_service: InventoryService
    quote_service: QuoteService
    order_service: OrderFulfillmentService
    response_safety_service: ResponseSafetyService
    ai: PydanticAiAgentAdapter
    workflow: WorkflowOrchestrator
    output: CsvEvaluationOutputAdapter
    evaluation: EvaluationRunner

    @classmethod
    def production(cls, config: AppConfig | None = None) -> "AppContainer":
        config = config or AppConfig.from_env()
        config.require_openai_key()

        persistence = SqlAlchemyPersistenceAdapter(
            database_url=config.database_url,
            data_dir=config.data_dir,
        )
        telemetry = LogfireTelemetryAdapter(
            log_path=config.logfire_log_file,
            sqlalchemy_engine=persistence.engine,
        )
        ids = UuidGeneratorAdapter()
        clock = SystemClockAdapter()
        catalog_matcher = CatalogMatchingService()
        resolver = CatalogItemResolver(catalog_matcher)
        inventory_service = InventoryService(persistence, resolver)
        quote_service = QuoteService(persistence, resolver)
        order_service = OrderFulfillmentService(
            inventory_service=inventory_service,
            quote_service=quote_service,
            transaction_repository=persistence,
            financial_report_repository=persistence,
            resolver=resolver,
            id_generator=ids,
        )
        response_safety_service = ResponseSafetyService()
        ai = PydanticAiAgentAdapter(
            model_name=config.openai_model_name,
            base_url=config.openai_base_url,
            api_key=config.openai_api_key,
            catalog_names=catalog_matcher.catalog_names(),
        )
        workflow = WorkflowOrchestrator(
            planner=ai,
            specialist_reporter=ai,
            responder=ai,
            catalog_matcher=catalog_matcher,
            inventory_service=inventory_service,
            quote_service=quote_service,
            order_service=order_service,
            response_safety_service=response_safety_service,
            telemetry=telemetry,
            id_generator=ids,
        )
        output = CsvEvaluationOutputAdapter(config.results_path)
        evaluation = EvaluationRunner(
            initializer=persistence,
            financial_reports=persistence,
            workflow=workflow,
            output=output,
            telemetry=telemetry,
            id_generator=ids,
            sample_path=str(config.data_dir / "quote_requests_sample.csv"),
            sleep_seconds=1.0,
        )

        return cls(
            config=config,
            persistence=persistence,
            telemetry=telemetry,
            ids=ids,
            clock=clock,
            catalog_matcher=catalog_matcher,
            resolver=resolver,
            inventory_service=inventory_service,
            quote_service=quote_service,
            order_service=order_service,
            response_safety_service=response_safety_service,
            ai=ai,
            workflow=workflow,
            output=output,
            evaluation=evaluation,
        )
