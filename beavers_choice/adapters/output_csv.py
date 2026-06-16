from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from beavers_choice.domain.models import EvaluationRow


def strip_trailing_response_whitespace(response: str) -> str:
    """Remove trailing whitespace from each response line before CSV output."""
    return "\n".join(line.rstrip() for line in str(response).splitlines())


def print_results_validation_summary(results_df: pd.DataFrame) -> None:
    """Print a concise reviewer-friendly summary of the saved evaluation CSV."""
    print(f"\nSaved {len(results_df)} rows to test_results.csv")

    if results_df.empty:
        print("No evaluation rows were generated.")
        return

    cash_values = results_df["cash_balance"].astype(float).reset_index(drop=True)
    previous_cash_values = pd.Series([50000.0, *cash_values.iloc[:-1].tolist()])
    cash_change_count = int((cash_values != previous_cash_values).sum())
    completed_order_references = int(
        results_df["response"]
        .str.contains("Order Reference", case=False, na=False)
        .sum()
    )
    partial_or_unfulfilled = int(
        results_df["response"]
        .str.contains(
            r"not fulfilled|unable to fulfill|cannot fulfill|rejected|"
            r"partially fulfilled|excluded",
            case=False,
            na=False,
            regex=True,
        )
        .sum()
    )

    print("Evaluation validation summary:")
    print(f"- Cash-balance changes: {cash_change_count}")
    print(f"- Completed order references: {completed_order_references}")
    print(f"- Partial or unfulfilled responses: {partial_or_unfulfilled}")

    preview = results_df[["request_id", "cash_balance", "response"]].copy()
    preview["response"] = (
        preview["response"]
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.slice(0, 160)
    )
    print("\nFirst five result rows:")
    print(preview.head().to_string(index=False))


class CsvEvaluationOutputAdapter:
    """CSV writer and validation summary printer."""

    def __init__(self, output_path: str | Path = "test_results.csv") -> None:
        self.output_path = Path(output_path)

    def write_results(self, rows: Iterable[EvaluationRow]) -> None:
        data = []
        for row in rows:
            row_data = row.model_dump()
            row_data["response"] = strip_trailing_response_whitespace(
                row_data["response"]
            )
            data.append(row_data)
        results_df = pd.DataFrame(data)
        results_df.to_csv(self.output_path, index=False)
        print_results_validation_summary(results_df)
