import pandas as pd
import numpy as np
import os
import time
import dotenv
import ast
import atexit
import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Union
from sqlalchemy import create_engine, Engine
from sqlalchemy.engine import Connection
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
import logfire

# Create an SQLite database
db_engine = create_engine("sqlite:///beaver_choice.db")

# List containing the different kinds of papers 
paper_supplies = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper",                         "category": "paper",        "unit_price": 0.05},
    {"item_name": "Letter-sized paper",              "category": "paper",        "unit_price": 0.06},
    {"item_name": "Cardstock",                        "category": "paper",        "unit_price": 0.15},
    {"item_name": "Colored paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Glossy paper",                     "category": "paper",        "unit_price": 0.20},
    {"item_name": "Matte paper",                      "category": "paper",        "unit_price": 0.18},
    {"item_name": "Recycled paper",                   "category": "paper",        "unit_price": 0.08},
    {"item_name": "Eco-friendly paper",               "category": "paper",        "unit_price": 0.12},
    {"item_name": "Poster paper",                     "category": "paper",        "unit_price": 0.25},
    {"item_name": "Banner paper",                     "category": "paper",        "unit_price": 0.30},
    {"item_name": "Kraft paper",                      "category": "paper",        "unit_price": 0.10},
    {"item_name": "Construction paper",               "category": "paper",        "unit_price": 0.07},
    {"item_name": "Wrapping paper",                   "category": "paper",        "unit_price": 0.15},
    {"item_name": "Glitter paper",                    "category": "paper",        "unit_price": 0.22},
    {"item_name": "Decorative paper",                 "category": "paper",        "unit_price": 0.18},
    {"item_name": "Letterhead paper",                 "category": "paper",        "unit_price": 0.12},
    {"item_name": "Legal-size paper",                 "category": "paper",        "unit_price": 0.08},
    {"item_name": "Crepe paper",                      "category": "paper",        "unit_price": 0.05},
    {"item_name": "Photo paper",                      "category": "paper",        "unit_price": 0.25},
    {"item_name": "Uncoated paper",                   "category": "paper",        "unit_price": 0.06},
    {"item_name": "Butcher paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Heavyweight paper",                "category": "paper",        "unit_price": 0.20},
    {"item_name": "Standard copy paper",              "category": "paper",        "unit_price": 0.04},
    {"item_name": "Bright-colored paper",             "category": "paper",        "unit_price": 0.12},
    {"item_name": "Patterned paper",                  "category": "paper",        "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},  # per plate
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},  # per cup
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},  # per napkin
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},  # per cup
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},  # per cover
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},  # per envelope
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},  # per sheet
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},  # per pad
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},  # per card
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},  # per flyer
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},  # per roll
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},  # per roll
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},  # per bag
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},  # per tag
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},  # per folder

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

# Given below are some utility functions you can use to implement your multi-agent system

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """
    Generate inventory for exactly a specified percentage of items from the full paper supply list.

    This function randomly selects exactly `coverage` × N items from the `paper_supplies` list,
    and assigns each selected item:
    - a random stock quantity between 200 and 800,
    - a minimum stock level between 50 and 150.

    The random seed ensures reproducibility of selection and stock levels.

    Args:
        paper_supplies (list): A list of dictionaries, each representing a paper item with
                               keys 'item_name', 'category', and 'unit_price'.
        coverage (float, optional): Fraction of items to include in the inventory (default is 0.4, or 40%).
        seed (int, optional): Random seed for reproducibility (default is 137).

    Returns:
        pd.DataFrame: A DataFrame with the selected items and assigned inventory values, including:
                      - item_name
                      - category
                      - unit_price
                      - current_stock
                      - min_stock_level
    """
    # Ensure reproducible random output
    np.random.seed(seed)

    # Calculate number of items to include based on coverage
    num_items = int(len(paper_supplies) * coverage)

    # Randomly select item indices without replacement
    selected_indices = np.random.choice(
        range(len(paper_supplies)),
        size=num_items,
        replace=False
    )

    # Extract selected items from paper_supplies list
    selected_items = [paper_supplies[i] for i in selected_indices]

    # Construct inventory records
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),  # Realistic stock range
            "min_stock_level": np.random.randint(50, 150)  # Reasonable threshold for reordering
        })

    # Return inventory as a pandas DataFrame
    return pd.DataFrame(inventory)

def init_database(db_engine: Engine = db_engine, seed: int = 137) -> Engine:    
    """
    Set up the Beaver's Choice database with all required tables and initial records.

    This function performs the following tasks:
    - Creates the 'transactions' table for logging stock orders and sales
    - Loads customer inquiries from 'quote_requests.csv' into a 'quote_requests' table
    - Loads previous quotes from 'quotes.csv' into a 'quotes' table, extracting useful metadata
    - Generates a random subset of paper inventory using `generate_sample_inventory`
    - Inserts initial financial records including available cash and starting stock levels

    Args:
        db_engine (Engine): A SQLAlchemy engine connected to the SQLite database.
        seed (int, optional): A random seed used to control reproducibility of inventory stock levels.
                              Default is 137.

    Returns:
        Engine: The same SQLAlchemy engine, after initializing all necessary tables and records.

    Raises:
        Exception: If an error occurs during setup, the exception is printed and raised.
    """
    try:
        # ----------------------------
        # 1. Create an empty 'transactions' table schema
        # ----------------------------
        transactions_schema = pd.DataFrame({
            "id": [],
            "item_name": [],
            "transaction_type": [],  # 'stock_orders' or 'sales'
            "units": [],             # Quantity involved
            "price": [],             # Total price for the transaction
            "transaction_date": [],  # ISO-formatted date
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)

        # Set a consistent starting date
        initial_date = datetime(2025, 1, 1).isoformat()

        # ----------------------------
        # 2. Load and initialize 'quote_requests' table
        # ----------------------------
        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 3. Load and transform 'quotes' table
        # ----------------------------
        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        # Unpack metadata fields (job_type, order_size, event_type) if present
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))

        # Retain only relevant columns
        quotes_df = quotes_df[[
            "request_id",
            "total_amount",
            "quote_explanation",
            "order_date",
            "job_type",
            "order_size",
            "event_type"
        ]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 4. Generate inventory and seed stock
        # ----------------------------
        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        # Seed initial transactions
        initial_transactions = []

        # Add a starting cash balance via a dummy sales transaction
        initial_transactions.append({
            "item_name": None,
            "transaction_type": "sales",
            "units": None,
            "price": 50000.0,
            "transaction_date": initial_date,
        })

        # Add one stock order transaction per inventory item
        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"],
                "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date,
            })

        # Commit transactions to database
        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)

        # Save the inventory reference table
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
    connection: Optional[Connection] = None,
) -> int:
    """
    This function records a transaction of type 'stock_orders' or 'sales' with a specified
    item name, quantity, total price, and transaction date into the 'transactions' table of the database.

    Args:
        item_name (str): The name of the item involved in the transaction.
        transaction_type (str): Either 'stock_orders' or 'sales'.
        quantity (int): Number of units involved in the transaction.
        price (float): Total price of the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    Raises:
        ValueError: If `transaction_type` is not 'stock_orders' or 'sales'.
        Exception: For other database or execution errors.
    """
    try:
        # Convert datetime to ISO string if necessary
        date_str = date.isoformat() if isinstance(date, datetime) else date

        # Validate transaction type
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        insert_query = text(
            """
            INSERT INTO transactions (
                item_name,
                transaction_type,
                units,
                price,
                transaction_date
            )
            VALUES (
                :item_name,
                :transaction_type,
                :units,
                :price,
                :transaction_date
            )
            """
        )
        params = {
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str,
        }

        def insert_with_connection(active_connection: Connection) -> int:
            active_connection.execute(insert_query, params)
            transaction_id = active_connection.execute(
                text("SELECT last_insert_rowid()")
            ).scalar_one()
            return int(transaction_id)

        if connection is not None:
            return insert_with_connection(connection)

        with db_engine.begin() as active_connection:
            return insert_with_connection(active_connection)

    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """
    Retrieve a snapshot of available inventory as of a specific date.

    This function calculates the net quantity of each item by summing 
    all stock orders and subtracting all sales up to and including the given date.

    Only items with positive stock are included in the result.

    Args:
        as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    # SQL query to compute stock levels per item as of the given date
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """

    # Execute the query with the date parameter
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})

    # Convert the result into a dictionary {item_name: stock}
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """
    Retrieve the stock level of a specific item as of a given date.

    This function calculates the net stock by summing all 'stock_orders' and 
    subtracting all 'sales' transactions for the specified item up to the given date.

    Args:
        item_name (str): The name of the item to look up.
        as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock.

    Returns:
        pd.DataFrame: A single-row DataFrame with columns 'item_name' and 'current_stock'.
    """
    # Convert date to ISO string format if it's a datetime object
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # SQL query to compute net stock level for the item
    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
        AND transaction_date <= :as_of_date
    """

    # Execute query and return result as a DataFrame
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": as_of_date},
    )

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date based on the requested order quantity and a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        input_date_str (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # Debug log (comment out in production if needed)
    print(f"FUNC (get_supplier_delivery_date): Calculating for qty {quantity} from date string '{input_date_str}'")

    # Attempt to parse the input date
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        # Fallback to current date on format error
        print(f"WARN (get_supplier_delivery_date): Invalid date format '{input_date_str}', using today as base.")
        input_date_dt = datetime.now()

    # Determine delivery delay based on quantity
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    # Add delivery days to the starting date
    delivery_date_dt = input_date_dt + timedelta(days=days)

    # Return formatted delivery date
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """
    Calculate the current cash balance as of a specified date.

    The balance is computed by subtracting total stock purchase costs ('stock_orders')
    from total revenue ('sales') recorded in the transactions table up to the given date.

    Args:
        as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    Returns:
        float: Net cash balance as of the given date. Returns 0.0 if no transactions exist or an error occurs.
    """
    try:
        # Convert date to ISO format if it's a datetime object
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()

        # Query all transactions on or before the specified date
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": as_of_date},
        )

        # Compute the difference between sales and stock purchases
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)

        return 0.0

    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0


def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report for the company as of a specific date.

    This includes:
    - Cash balance
    - Inventory valuation
    - Combined asset total
    - Itemized inventory breakdown
    - Top 5 best-selling products

    Args:
        as_of_date (str or datetime): The date (inclusive) for which to generate the report.

    Returns:
        Dict: A dictionary containing the financial report fields:
            - 'as_of_date': The date of the report
            - 'cash_balance': Total cash available
            - 'inventory_value': Total value of inventory
            - 'total_assets': Combined cash and inventory value
            - 'inventory_summary': List of items with stock and valuation details
            - 'top_selling_products': List of top 5 products by revenue
    """
    # Normalize date input
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # Get current cash balance
    cash = get_cash_balance(as_of_date)

    # Get current inventory snapshot
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    # Compute total inventory value and summary by item
    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    # Identify top-selling products by revenue
    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """
    Retrieve a list of historical quotes that match any of the provided search terms.

    The function searches both the original customer request (from `quote_requests`) and
    the explanation for the quote (from `quotes`) for each keyword. Results are sorted by
    most recent order date and limited by the `limit` parameter.

    Args:
        search_terms (List[str]): List of terms to match against customer requests and explanations.
        limit (int, optional): Maximum number of quote records to return. Default is 5.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary with fields:
            - original_request
            - total_amount
            - quote_explanation
            - job_type
            - order_size
            - event_type
            - order_date
    """
    conditions = []
    params = {}

    # Build SQL WHERE clause using LIKE filters for each search term
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    # Combine conditions; fallback to always-true if no terms provided
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Final SQL query to join quotes with quote_requests
    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """

    # Execute parameterized query
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]


# YOUR MULTI AGENT STARTS HERE
# Set up and load your env parameters and instantiate your model.

dotenv.load_dotenv()

LOGFIRE_LOG_PATH = Path(os.getenv("LOGFIRE_LOG_FILE", "logfire.log"))
LOGFIRE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOGFIRE_LOG_STREAM = LOGFIRE_LOG_PATH.open(
    "a",
    encoding="utf-8",
    buffering=1,
)

logfire.configure(
    service_name="beavers-choice-multi-agent",
    send_to_logfire=False,
    console=logfire.ConsoleOptions(
        output=LOGFIRE_LOG_STREAM,
        span_style="show-parents",
        include_timestamps=True,
        include_tags=True,
        verbose=True,
        show_project_link=False,
    ),
)
logfire.instrument_pydantic_ai()
logfire.instrument_sqlalchemy(engine=db_engine)


def _shutdown_logfire() -> None:
    """Flush local traces before the Python process exits."""
    logfire.force_flush()
    LOGFIRE_LOG_STREAM.flush()
    LOGFIRE_LOG_STREAM.close()


atexit.register(_shutdown_logfire)

OPENAI_API_KEY = os.getenv("UDACITY_OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv(
    "UDACITY_OPENAI_API_BASE_URL",
    "https://openai.vocareum.com/v1",
)
OPENAI_MODEL_NAME = os.getenv("UDACITY_OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "UDACITY_OPENAI_API_KEY is required. Add it to .env before running the project."
    )

agent_model = OpenAIChatModel(
    OPENAI_MODEL_NAME,
    provider=OpenAIProvider(
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
    ),
)

CATALOG_BY_NAME = {
    item["item_name"].casefold(): item
    for item in paper_supplies
}
CATALOG_NAMES = [item["item_name"] for item in paper_supplies]


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


class InquiryPlan(BaseModel):
    """Validated routing decision produced by the decision orchestrator."""

    route: Literal["inventory", "quote", "order", "general"] = Field(
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
    items: List[RequestedItem] = Field(default_factory=list)
    unmatched_items: List[str] = Field(
        default_factory=list,
        description="Requested products that cannot be mapped to the catalog.",
    )
    customer_summary: str = Field(
        description="A concise summary of the customer's intent and constraints."
    )


@dataclass
class SpecialistDeps:
    """Validated inputs and an idempotent result cache for one specialist run."""

    plan: InquiryPlan
    cached_result: Optional[Dict[str, Any]] = None
    result_lock: threading.Lock = field(default_factory=threading.Lock)


def _parse_date(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.split("T")[0])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format: {value!r}") from exc


def _validated_catalog_items(items: List[RequestedItem]) -> List[Dict[str, Any]]:
    combined: Dict[str, Dict[str, Any]] = {}

    for requested_item in items:
        catalog_item = CATALOG_BY_NAME.get(requested_item.item_name.strip().casefold())
        if catalog_item is None:
            raise ValueError(
                f"Unknown catalog item {requested_item.item_name!r}. "
                "Use an exact item_name from the catalog."
            )

        exact_name = catalog_item["item_name"]
        if exact_name not in combined:
            combined[exact_name] = {
                **catalog_item,
                "quantity": 0,
                "requested_descriptions": [],
            }

        combined[exact_name]["quantity"] += requested_item.quantity
        if requested_item.requested_description:
            combined[exact_name]["requested_descriptions"].append(
                requested_item.requested_description
            )

    return list(combined.values())


def _minimum_stock_level(item_name: str) -> int:
    result = pd.read_sql(
        """
        SELECT min_stock_level
        FROM inventory
        WHERE item_name = :item_name
        LIMIT 1
        """,
        db_engine,
        params={"item_name": item_name},
    )
    if result.empty:
        return 100
    return int(result.iloc[0]["min_stock_level"])


def _inventory_snapshot(
    items: List[RequestedItem],
    as_of_date: str,
    required_by: Optional[str] = None,
) -> Dict[str, Any]:
    request_date = _parse_date(as_of_date, "as_of_date")
    deadline = _parse_date(required_by, "required_by") if required_by else None
    complete_inventory = get_all_inventory(as_of_date)
    lines = []

    for item in _validated_catalog_items(items):
        stock_result = get_stock_level(item["item_name"], as_of_date)
        exact_stock = int(stock_result.iloc[0]["current_stock"])
        snapshot_stock = int(complete_inventory.get(item["item_name"], 0))
        current_stock = exact_stock
        minimum_stock = _minimum_stock_level(item["item_name"])
        restock_quantity = max(
            0,
            item["quantity"] + minimum_stock - current_stock,
        )
        supplier_delivery = (
            get_supplier_delivery_date(as_of_date, restock_quantity)
            if restock_quantity
            else request_date.strftime("%Y-%m-%d")
        )
        deliverable = (
            deadline is None
            or _parse_date(supplier_delivery, "supplier_delivery") <= deadline
        )

        lines.append(
            {
                "item_name": item["item_name"],
                "requested_quantity": item["quantity"],
                "current_stock": current_stock,
                "snapshot_stock": snapshot_stock,
                "minimum_stock_level": minimum_stock,
                "available_without_restock": current_stock >= item["quantity"],
                "restock_quantity": restock_quantity,
                "supplier_delivery_date": supplier_delivery,
                "deliverable_by_deadline": deliverable,
            }
        )

    return {
        "as_of_date": request_date.strftime("%Y-%m-%d"),
        "required_by": deadline.strftime("%Y-%m-%d") if deadline else None,
        "inventory_items_in_stock": len(complete_inventory),
        "all_items_deliverable": all(
            line["deliverable_by_deadline"] for line in lines
        ),
        "items": lines,
    }


def _discount_rate(total_quantity: int) -> float:
    if total_quantity >= 5000:
        return 0.15
    if total_quantity >= 2000:
        return 0.10
    if total_quantity >= 500:
        return 0.05
    return 0.0


def _historical_quote_examples(
    item_names: List[str],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    examples: List[Dict[str, Any]] = []
    seen = set()

    for item_name in item_names:
        search_candidates = [item_name]
        meaningful_words = [
            word
            for word in re.findall(r"[A-Za-z]+", item_name)
            if len(word) >= 4
        ]
        if meaningful_words:
            search_candidates.append(meaningful_words[0])

        for search_term in search_candidates:
            matches = search_quote_history([search_term], limit=2)
            for match in matches:
                key = (
                    match["original_request"],
                    match["total_amount"],
                )
                if key not in seen:
                    seen.add(key)
                    examples.append(match)
                if len(examples) >= limit:
                    return examples

    return examples


def _calculate_quote(
    items: List[RequestedItem],
    request_date: str,
) -> Dict[str, Any]:
    _parse_date(request_date, "request_date")
    catalog_items = _validated_catalog_items(items)
    total_quantity = sum(item["quantity"] for item in catalog_items)
    discount_rate = _discount_rate(total_quantity)

    lines = []
    base_total = 0.0
    for item in catalog_items:
        subtotal = round(item["quantity"] * item["unit_price"], 2)
        discounted_subtotal = round(subtotal * (1 - discount_rate), 2)
        base_total += subtotal
        lines.append(
            {
                "item_name": item["item_name"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "subtotal": subtotal,
                "discounted_subtotal": discounted_subtotal,
            }
        )

    total = round(base_total * (1 - discount_rate), 2)
    if lines:
        rounding_difference = round(
            total - sum(line["discounted_subtotal"] for line in lines),
            2,
        )
        lines[-1]["discounted_subtotal"] = round(
            lines[-1]["discounted_subtotal"] + rounding_difference,
            2,
        )

    return {
        "request_date": request_date,
        "total_quantity": total_quantity,
        "base_total": round(base_total, 2),
        "discount_rate": discount_rate,
        "discount_amount": round(base_total - total, 2),
        "total": total,
        "lines": lines,
        "historical_examples": _historical_quote_examples(
            [item["item_name"] for item in catalog_items]
        ),
    }


"""Set up tools for your agents to use, these should be methods that combine the database functions above
 and apply criteria to them to ensure that the flow of the system is correct."""


# Tools for inventory agent

def inspect_inventory(
    items: List[RequestedItem],
    as_of_date: str,
    required_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Check stock, safety-stock restocking needs, and deadline feasibility."""
    return _inventory_snapshot(items, as_of_date, required_by)


# Tools for quoting agent

def prepare_quote(
    items: List[RequestedItem],
    request_date: str,
) -> Dict[str, Any]:
    """Create a deterministic itemized quote and retrieve relevant quote history."""
    return _calculate_quote(items, request_date)


# Tools for ordering agent

def fulfill_order(
    items: List[RequestedItem],
    order_date: str,
    required_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate, restock, and record an order without overspending available cash."""
    inventory = _inventory_snapshot(items, order_date, required_by)
    blocked_items = [
        line["item_name"]
        for line in inventory["items"]
        if not line["deliverable_by_deadline"]
    ]
    if blocked_items:
        return {
            "status": "rejected",
            "reason": "Supplier lead time exceeds the requested delivery date.",
            "blocked_items": blocked_items,
            "inventory": inventory,
        }

    quote = _calculate_quote(items, order_date)
    catalog_items = {
        item["item_name"]: item
        for item in _validated_catalog_items(items)
    }
    restock_cost = round(
        sum(
            line["restock_quantity"]
            * catalog_items[line["item_name"]]["unit_price"]
            for line in inventory["items"]
        ),
        2,
    )
    available_cash = get_cash_balance(order_date)
    if restock_cost > available_cash:
        return {
            "status": "rejected",
            "reason": "Insufficient cash to purchase the required restock.",
            "required_cash": restock_cost,
            "available_cash": round(available_cash, 2),
        }

    order_reference = (
        f"BC-{order_date.replace('-', '')}-{uuid.uuid4().hex[:8].upper()}"
    )
    transaction_ids = {
        "stock_orders": [],
        "sales": [],
    }

    with db_engine.begin() as connection:
        for item_name, item in catalog_items.items():
            connection.execute(
                text(
                    """
                    INSERT INTO inventory (
                        item_name,
                        category,
                        unit_price,
                        current_stock,
                        min_stock_level
                    )
                    SELECT
                        :item_name,
                        :category,
                        :unit_price,
                        0,
                        100
                    WHERE NOT EXISTS (
                        SELECT 1 FROM inventory WHERE item_name = :item_name
                    )
                    """
                ),
                {
                    "item_name": item_name,
                    "category": item["category"],
                    "unit_price": item["unit_price"],
                },
            )

        for inventory_line in inventory["items"]:
            restock_quantity = inventory_line["restock_quantity"]
            if restock_quantity:
                unit_price = catalog_items[inventory_line["item_name"]]["unit_price"]
                transaction_id = create_transaction(
                    item_name=inventory_line["item_name"],
                    transaction_type="stock_orders",
                    quantity=restock_quantity,
                    price=round(restock_quantity * unit_price, 2),
                    date=order_date,
                    connection=connection,
                )
                transaction_ids["stock_orders"].append(transaction_id)

        for quote_line in quote["lines"]:
            transaction_id = create_transaction(
                item_name=quote_line["item_name"],
                transaction_type="sales",
                quantity=quote_line["quantity"],
                price=quote_line["discounted_subtotal"],
                date=order_date,
                connection=connection,
            )
            transaction_ids["sales"].append(transaction_id)

    delivery_dates = [
        line["supplier_delivery_date"]
        for line in inventory["items"]
    ]
    scheduled_delivery = max(delivery_dates) if delivery_dates else order_date
    financial_report = generate_financial_report(order_date)

    return {
        "status": "fulfilled",
        "order_reference": order_reference,
        "order_date": order_date,
        "scheduled_delivery": scheduled_delivery,
        "required_by": required_by,
        "charged_total": quote["total"],
        "discount_rate": quote["discount_rate"],
        "restock_cost": restock_cost,
        "transaction_ids": transaction_ids,
        "post_order_financial_state": {
            "cash_balance": round(float(financial_report["cash_balance"]), 2),
            "inventory_value": round(float(financial_report["inventory_value"]), 2),
            "total_assets": round(float(financial_report["total_assets"]), 2),
        },
        "items": quote["lines"],
    }


# Set up your agents and create an orchestration agent that will manage them.

catalog_prompt = "\n".join(f"- {name}" for name in CATALOG_NAMES)

decision_orchestrator_agent = Agent(
    agent_model,
    output_type=InquiryPlan,
    instructions="""
You are Beaver's Choice decision orchestrator and data validation agent.
Parse the customer inquiry, validate dates and quantities, and select one route.

Routing rules:
- "order": the customer asks to buy, place an order, confirm delivery, or supply items.
- "quote": the customer asks only for prices, estimates, or quote discussion.
- "inventory": the customer asks only about availability or stock.
- "general": no specialist can validly handle the request.

Map products only to exact catalog names from the list below. Preserve quantities.
Put products that cannot reasonably map to the catalog in unmatched_items.
Common wording guidance:
- printer or copier paper usually maps to "Standard copy paper"
- glossy paper maps to "Glossy paper"
- matte paper maps to "Matte paper"
- cardstock maps to "Cardstock"
- streamers maps to "Party streamers"
- washi tape maps to "Decorative adhesive tape (washi tape)"
- poster boards can map to "Large poster paper (24x36 inches)"
- balloons and unsupported paper sizes with no catalog equivalent remain unmatched

The prompt includes an explicit Date of request; use it as request_date.
Convert any delivery deadline to YYYY-MM-DD. Never invent quantities or products.
""",
)


@decision_orchestrator_agent.instructions
def add_catalog_to_orchestrator() -> str:
    """Supply the current catalog to the validation agent at run time."""
    return f"Use only these exact Beaver's Choice catalog item names:\n{catalog_prompt}"


inventory_agent = Agent(
    agent_model,
    deps_type=SpecialistDeps,
    instructions="""
You are Beaver's Choice inventory specialist.
You must call inventory_lookup_tool using the validated plan supplied as dependencies.
Explain current stock, restocking needs, supplier timing, and whether the requested
deadline is feasible. Treat restocking needed to preserve minimum stock as a real
restocking recommendation even when enough units are currently available.
Never guess stock values or rename catalog items.
""",
)


@inventory_agent.instructions
def add_inventory_plan(ctx: RunContext[SpecialistDeps]) -> str:
    """Inject the orchestrator-validated plan into the inventory agent."""
    return "Validated inquiry plan:\n" + ctx.deps.plan.model_dump_json(indent=2)


@inventory_agent.tool
def inventory_lookup_tool(ctx: RunContext[SpecialistDeps]) -> Dict[str, Any]:
    """Inspect stock and delivery feasibility for the validated inquiry plan."""
    with ctx.deps.result_lock:
        if ctx.deps.cached_result is None:
            plan = ctx.deps.plan
            ctx.deps.cached_result = inspect_inventory(
                plan.items,
                plan.request_date,
                plan.required_by,
            )
        return ctx.deps.cached_result


quote_agent = Agent(
    agent_model,
    deps_type=SpecialistDeps,
    instructions="""
You are Beaver's Choice quote specialist.
You must call quote_calculation_tool using the validated plan supplied as dependencies.
Present an itemized quote, the bulk discount, final total, and briefly mention how
relevant historical quote examples informed the explanation when examples exist.
Never change tool-calculated prices or use unsupported items.
""",
)


@quote_agent.instructions
def add_quote_plan(ctx: RunContext[SpecialistDeps]) -> str:
    """Inject the orchestrator-validated plan into the quote agent."""
    return "Validated inquiry plan:\n" + ctx.deps.plan.model_dump_json(indent=2)


@quote_agent.tool
def quote_calculation_tool(ctx: RunContext[SpecialistDeps]) -> Dict[str, Any]:
    """Calculate itemized pricing for the validated inquiry plan."""
    with ctx.deps.result_lock:
        if ctx.deps.cached_result is None:
            plan = ctx.deps.plan
            ctx.deps.cached_result = prepare_quote(
                plan.items,
                plan.request_date,
            )
        return ctx.deps.cached_result


order_agent = Agent(
    agent_model,
    deps_type=SpecialistDeps,
    instructions="""
You are Beaver's Choice order fulfillment specialist.
You must call order_fulfillment_tool using the validated plan supplied as dependencies.
Only claim an order is confirmed when the tool returns status "fulfilled".
Report the order reference, charged total, delivery schedule, and any rejection
reason exactly as returned by the tool. Do not reveal transaction IDs, available
cash, inventory valuation, total assets, or restocking costs to the customer.
""",
)


@order_agent.instructions
def add_order_plan(ctx: RunContext[SpecialistDeps]) -> str:
    """Inject the orchestrator-validated plan into the order agent."""
    return "Validated inquiry plan:\n" + ctx.deps.plan.model_dump_json(indent=2)


@order_agent.tool
def order_fulfillment_tool(ctx: RunContext[SpecialistDeps]) -> Dict[str, Any]:
    """Fulfill the validated order once and return its authoritative result."""
    with ctx.deps.result_lock:
        if ctx.deps.cached_result is None:
            plan = ctx.deps.plan
            ctx.deps.cached_result = fulfill_order(
                plan.items,
                plan.request_date,
                plan.required_by,
            )
        return ctx.deps.cached_result


customer_inquiry_agent = Agent(
    agent_model,
    instructions="""
You are the customer-facing Beaver's Choice inquiry agent.
Create one concise, professional response from the validated plan and specialist
reports supplied in the prompt. Use only those facts. Clearly identify unsupported
items, prices, discounts, delivery dates, order status, and next steps. Do not invent
stock, products, order references, deadlines, or guarantees. A request_date is only
the date the inquiry was submitted; mention a delivery deadline only when required_by
is present in the validated plan. Never reveal internal cash balances, inventory
valuations, total assets, transaction IDs, restocking costs, or internal errors.
Do not emit placeholder names or signatures. If unsupported items were excluded,
describe the result as partially fulfilled rather than fully fulfilled.
""",
)


def call_multi_agent_system(customer_request: str) -> str:
    """Validate, route, execute specialist agents, and synthesize one response."""
    inquiry_id = uuid.uuid4().hex
    with logfire.span(
        "Process customer inquiry",
        inquiry_id=inquiry_id,
        customer_request=customer_request,
    ):
        try:
            plan_result = decision_orchestrator_agent.run_sync(customer_request)
            plan = plan_result.output

            explicit_request_date = re.search(
                r"Date of request:\s*(\d{4}-\d{2}-\d{2})",
                customer_request,
                flags=re.IGNORECASE,
            )
            if explicit_request_date:
                plan.request_date = explicit_request_date.group(1)

            _parse_date(plan.request_date, "request_date")
            if plan.required_by:
                _parse_date(plan.required_by, "required_by")

            logfire.info(
                "Inquiry validated and routed",
                inquiry_id=inquiry_id,
                route=plan.route,
                request_date=plan.request_date,
                required_by=plan.required_by,
                item_count=len(plan.items),
                unmatched_items=plan.unmatched_items,
            )

            plan_json = plan.model_dump_json(indent=2)
            specialist_reports: Dict[str, str] = {}
            specialist_results: Dict[str, Dict[str, Any]] = {}

            if plan.items and plan.route in {"inventory", "quote", "order"}:
                inventory_deps = SpecialistDeps(plan=plan)
                inventory_result = inventory_agent.run_sync(
                    "Review this validated inquiry plan:\n" + plan_json,
                    deps=inventory_deps,
                )
                specialist_reports["inventory"] = inventory_result.output
                if inventory_deps.cached_result is None:
                    inventory_deps.cached_result = inspect_inventory(
                        plan.items,
                        plan.request_date,
                        plan.required_by,
                    )
                specialist_results["inventory"] = inventory_deps.cached_result

            if plan.items and plan.route in {"quote", "order"}:
                quote_deps = SpecialistDeps(plan=plan)
                quote_result = quote_agent.run_sync(
                    "Prepare pricing for this validated inquiry plan:\n" + plan_json,
                    deps=quote_deps,
                )
                specialist_reports["quote"] = quote_result.output
                if quote_deps.cached_result is None:
                    quote_deps.cached_result = prepare_quote(
                        plan.items,
                        plan.request_date,
                    )
                specialist_results["quote"] = quote_deps.cached_result

            if plan.items and plan.route == "order":
                order_deps = SpecialistDeps(plan=plan)
                order_result = order_agent.run_sync(
                    "Fulfill this validated inquiry plan:\n"
                    + plan_json
                    + "\nInventory report:\n"
                    + specialist_reports.get("inventory", "")
                    + "\nQuote report:\n"
                    + specialist_reports.get("quote", ""),
                    deps=order_deps,
                )
                specialist_reports["order"] = order_result.output
                if order_deps.cached_result is None:
                    order_deps.cached_result = fulfill_order(
                        plan.items,
                        plan.request_date,
                        plan.required_by,
                    )
                specialist_results["order"] = order_deps.cached_result

            customer_result = customer_inquiry_agent.run_sync(
                "Original customer inquiry:\n"
                + customer_request
                + "\n\nValidated plan:\n"
                + plan_json
                + "\n\nSpecialist reports:\n"
                + json.dumps(specialist_reports, indent=2)
                + "\n\nAuthoritative specialist tool results:\n"
                + json.dumps(specialist_results, indent=2)
            )
            logfire.info(
                "Inquiry completed",
                inquiry_id=inquiry_id,
                route=plan.route,
                specialist_agents=list(specialist_reports),
            )
            return customer_result.output
        except Exception as exc:
            logfire.exception(
                "Inquiry workflow failed",
                inquiry_id=inquiry_id,
                error_type=type(exc).__name__,
            )
            return (
                "We could not complete this inquiry at this time. "
                f"Please contact support and provide reference {inquiry_id}."
            )

# Run your test scenarios by writing them here. Make sure to keep track of them.

def run_test_scenarios():
    test_run_id = uuid.uuid4().hex
    logfire.info(
        "Starting complete test scenario run",
        test_run_id=test_run_id,
    )

    print("Initializing Database...")
    init_database()
    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    # INITIALIZE YOUR MULTI AGENT SYSTEM HERE
    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")
        request_id = idx + 1

        print(f"\n=== Request {request_id} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = (
            f"Customer role: {row['job']}. Event: {row['event']}. "
            f"Request: {row['request']} (Date of request: {request_date})"
        )

        # USE YOUR MULTI AGENT SYSTEM TO HANDLE THE REQUEST
        with logfire.span(
            "Run customer test scenario",
            test_run_id=test_run_id,
            request_id=request_id,
            request_date=request_date,
            customer_job=row["job"],
            event=row["event"],
        ):
            response = call_multi_agent_system(request_with_date)

        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(1)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    logfire.info(
        "Completed test scenario run",
        test_run_id=test_run_id,
        scenario_count=len(results),
        final_cash=final_report["cash_balance"],
        final_inventory=final_report["inventory_value"],
        results_file="test_results.csv",
        logfire_file=str(LOGFIRE_LOG_PATH),
    )
    logfire.force_flush()
    return results


if __name__ == "__main__":
    results = run_test_scenarios()
