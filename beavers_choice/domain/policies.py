from __future__ import annotations

from datetime import datetime, timedelta

from beavers_choice.domain.errors import InvalidDateError


def parse_date(value: str, field_name: str) -> datetime:
    """Parse an ISO-like date and raise a domain-specific validation error."""
    try:
        return datetime.fromisoformat(value.split("T")[0])
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidDateError(
            f"{field_name} must use YYYY-MM-DD format: {value!r}"
        ) from exc


def supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """Estimate supplier delivery date using Beaver's Choice lead-time rules."""
    input_date_dt = parse_date(input_date_str, "input_date_str")
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7
    return (input_date_dt + timedelta(days=days)).strftime("%Y-%m-%d")


def discount_rate(total_quantity: int) -> float:
    """Apply quantity discount thresholds."""
    if total_quantity >= 5000:
        return 0.15
    if total_quantity >= 2000:
        return 0.10
    if total_quantity >= 500:
        return 0.05
    return 0.0


def is_deliverable_by_deadline(delivery_date: str, required_by: str | None) -> bool:
    """Return whether a supplier delivery date satisfies the customer deadline."""
    if not required_by:
        return True
    return parse_date(delivery_date, "delivery_date") <= parse_date(
        required_by,
        "required_by",
    )

