from __future__ import annotations

import time
from typing import List

import pandas as pd

from beavers_choice.domain.models import EvaluationRow
from beavers_choice.ports.output import EvaluationOutputPort
from beavers_choice.ports.repositories import FinancialReportRepository, QuoteHistoryRepository
from beavers_choice.ports.telemetry import TelemetryPort
from beavers_choice.ports.ids import IdGeneratorPort
from beavers_choice.app.workflow import WorkflowOrchestrator


class EvaluationRunner:
    """Run the full quote request sample through the workflow."""

    def __init__(
        self,
        initializer: QuoteHistoryRepository,
        financial_reports: FinancialReportRepository,
        workflow: WorkflowOrchestrator,
        output: EvaluationOutputPort,
        telemetry: TelemetryPort,
        id_generator: IdGeneratorPort,
        sample_path: str = "quote_requests_sample.csv",
        sleep_seconds: float = 1.0,
    ) -> None:
        self.initializer = initializer
        self.financial_reports = financial_reports
        self.workflow = workflow
        self.output = output
        self.telemetry = telemetry
        self.id_generator = id_generator
        self.sample_path = sample_path
        self.sleep_seconds = sleep_seconds

    def run(self) -> List[EvaluationRow]:
        test_run_id = self.id_generator.inquiry_id()
        self.telemetry.info(
            "Starting complete test scenario run",
            test_run_id=test_run_id,
        )

        print("Initializing Database...")
        self.initializer.initialize()
        try:
            quote_requests_sample = pd.read_csv(self.sample_path)
            quote_requests_sample["request_date"] = pd.to_datetime(
                quote_requests_sample["request_date"],
                format="%m/%d/%y",
                errors="coerce",
            )
            quote_requests_sample.dropna(subset=["request_date"], inplace=True)
            quote_requests_sample = quote_requests_sample.sort_values("request_date")
        except Exception as exc:
            print(f"FATAL: Error loading test data: {exc}")
            return []

        initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
        report = self.financial_reports.generate_financial_report(initial_date)
        current_cash = report.cash_balance
        current_inventory = report.inventory_value

        results: list[EvaluationRow] = []
        for idx, row in quote_requests_sample.iterrows():
            request_date = row["request_date"].strftime("%Y-%m-%d")
            request_id = idx + 1

            print(f"\n=== Request {request_id} ===")
            print(f"Context: {row['job']} organizing {row['event']}")
            print(f"Request Date: {request_date}")
            print(f"Cash Balance: ${current_cash:.2f}")
            print(f"Inventory Value: ${current_inventory:.2f}")

            request_with_date = (
                f"Customer role: {row['job']}. Event: {row['event']}. "
                f"Request: {row['request']} (Date of request: {request_date})"
            )

            with self.telemetry.span(
                "Run customer test scenario",
                test_run_id=test_run_id,
                request_id=request_id,
                request_date=request_date,
                customer_job=row["job"],
                event=row["event"],
            ):
                response = self.workflow.response_for(request_with_date)

            report = self.financial_reports.generate_financial_report(request_date)
            current_cash = report.cash_balance
            current_inventory = report.inventory_value

            print(f"Response: {response}")
            print(f"Updated Cash: ${current_cash:.2f}")
            print(f"Updated Inventory: ${current_inventory:.2f}")

            results.append(
                EvaluationRow(
                    request_id=request_id,
                    request_date=request_date,
                    cash_balance=current_cash,
                    inventory_value=current_inventory,
                    response=response,
                )
            )

            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)

        final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
        final_report = self.financial_reports.generate_financial_report(final_date)
        print("\n===== FINAL FINANCIAL REPORT =====")
        print(f"Final Cash: ${final_report.cash_balance:.2f}")
        print(f"Final Inventory: ${final_report.inventory_value:.2f}")

        self.output.write_results(results)
        self.telemetry.info(
            "Completed test scenario run",
            test_run_id=test_run_id,
            scenario_count=len(results),
            final_cash=final_report.cash_balance,
            final_inventory=final_report.inventory_value,
            results_file="test_results.csv",
        )
        self.telemetry.flush()
        return results
