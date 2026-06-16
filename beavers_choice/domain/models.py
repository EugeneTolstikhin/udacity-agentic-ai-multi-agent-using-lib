from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Route = Literal["inventory", "quote", "order", "general"]
TransactionType = Literal["stock_orders", "sales"]


class CatalogItem(BaseModel):
    """A sellable Beaver's Choice catalog item."""

    item_name: str
    category: str
    unit_price: float


class ExtractedItem(BaseModel):
    """A raw customer item phrase extracted before catalog normalization."""

    item_description: str = Field(description="Customer's raw item wording.")
    quantity: int = Field(gt=0, description="Number of units requested.")


class CatalogMatch(BaseModel):
    """Deterministic match decision for one raw requested item."""

    original_description: str
    item_name: Optional[str] = None
    confidence: float
    strategy: Literal["exact", "alias", "fuzzy", "unmatched"]
    reason: str = ""


class RequestedItem(BaseModel):
    """A validated line item using an exact Beaver's Choice catalog name."""

    item_name: str = Field(
        description="Exact item_name from the Beaver's Choice catalog."
    )
    quantity: int = Field(gt=0, description="Number of units requested.")
    requested_description: str = Field(
        default="",
        description="The customer's original wording for this item.",
    )


class ExtractedInquiry(BaseModel):
    """Planner output before deterministic catalog matching."""

    route: Route = Field(
        description=(
            "inventory for availability questions, quote for pricing requests, "
            "order when the customer asks to buy or deliver items, otherwise general."
        )
    )
    request_date: str = Field(description="Request date in YYYY-MM-DD format.")
    required_by: Optional[str] = Field(
        default=None,
        description="Requested delivery date in YYYY-MM-DD format, if supplied.",
    )
    items: List[ExtractedItem] = Field(default_factory=list)
    unmatched_items: List[str] = Field(
        default_factory=list,
        description="Requested products the planner already knows are unsupported.",
    )
    customer_summary: str = Field(
        default="",
        description="A concise summary of the customer's intent and constraints.",
    )


class InquiryPlan(BaseModel):
    """Validated routing decision after deterministic catalog matching."""

    route: Route
    request_date: str
    required_by: Optional[str] = None
    items: List[RequestedItem] = Field(default_factory=list)
    unmatched_items: List[str] = Field(default_factory=list)
    customer_summary: str = ""
    match_details: List[CatalogMatch] = Field(default_factory=list)


class InventoryLine(BaseModel):
    item_name: str
    requested_quantity: int
    current_stock: int
    snapshot_stock: int
    minimum_stock_level: int
    available_without_restock: bool
    restock_quantity: int
    supplier_delivery_date: str
    deliverable_by_deadline: bool


class InventoryResult(BaseModel):
    as_of_date: str
    required_by: Optional[str] = None
    inventory_items_in_stock: int
    all_items_deliverable: bool
    items: List[InventoryLine]


class QuoteLine(BaseModel):
    item_name: str
    quantity: int
    unit_price: float
    subtotal: float
    discounted_subtotal: float


class QuoteResult(BaseModel):
    request_date: str
    total_quantity: int
    base_total: float
    discount_rate: float
    discount_amount: float
    total: float
    lines: List[QuoteLine]
    historical_examples: List[Dict[str, Any]] = Field(default_factory=list)


class FinancialReport(BaseModel):
    as_of_date: str
    cash_balance: float
    inventory_value: float
    total_assets: float


class TransactionRecord(BaseModel):
    id: Optional[int] = None
    item_name: Optional[str] = None
    transaction_type: TransactionType
    units: Optional[int] = None
    price: float
    transaction_date: str


class OrderResult(BaseModel):
    status: Literal["fulfilled", "rejected"]
    reason: Optional[str] = None
    order_reference: Optional[str] = None
    order_date: Optional[str] = None
    scheduled_delivery: Optional[str] = None
    required_by: Optional[str] = None
    charged_total: Optional[float] = None
    discount_rate: Optional[float] = None
    restock_cost: Optional[float] = None
    transaction_ids: Dict[str, List[int]] = Field(
        default_factory=lambda: {"stock_orders": [], "sales": []}
    )
    post_order_financial_state: Optional[Dict[str, float]] = None
    items: List[QuoteLine] = Field(default_factory=list)
    blocked_items: List[str] = Field(default_factory=list)
    inventory: Optional[InventoryResult] = None
    required_cash: Optional[float] = None
    available_cash: Optional[float] = None


class SpecialistReports(BaseModel):
    inventory: Optional[str] = None
    quote: Optional[str] = None
    order: Optional[str] = None


class SpecialistResults(BaseModel):
    inventory: Optional[InventoryResult] = None
    quote: Optional[QuoteResult] = None
    order: Optional[OrderResult] = None


class WorkflowResult(BaseModel):
    inquiry_id: str
    plan: InquiryPlan
    specialist_reports: SpecialistReports
    specialist_results: SpecialistResults
    response: str


class EvaluationRow(BaseModel):
    request_id: int
    request_date: str
    cash_balance: float
    inventory_value: float
    response: str

