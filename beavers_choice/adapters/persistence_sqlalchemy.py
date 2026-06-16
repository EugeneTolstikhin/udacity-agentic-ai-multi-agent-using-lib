from __future__ import annotations

import ast
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Type

import numpy as np
import pandas as pd
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.sql import text

from beavers_choice.domain.catalog import PAPER_SUPPLIES
from beavers_choice.domain.models import (
    CatalogItem,
    FinancialReport,
    TransactionRecord,
    TransactionType,
)
from beavers_choice.domain.services import financial_report_from_values


def generate_sample_inventory(
    paper_supplies: list[dict] | None = None,
    coverage: float = 0.4,
    seed: int = 137,
) -> pd.DataFrame:
    """Generate deterministic starter inventory as a Pandas adapter detail."""
    supply_rows = paper_supplies or [item.model_dump() for item in PAPER_SUPPLIES]
    np.random.seed(seed)
    num_items = int(len(supply_rows) * coverage)
    selected_indices = np.random.choice(
        range(len(supply_rows)),
        size=num_items,
        replace=False,
    )
    selected_items = [supply_rows[i] for i in selected_indices]
    inventory = []
    for item in selected_items:
        inventory.append(
            {
                "item_name": item["item_name"],
                "category": item["category"],
                "unit_price": item["unit_price"],
                "current_stock": np.random.randint(200, 800),
                "min_stock_level": np.random.randint(50, 150),
            }
        )
    return pd.DataFrame(inventory)


class SqlAlchemyTransactionUnitOfWork:
    """SQLAlchemy-backed atomic transaction boundary."""

    def __init__(self, adapter: "SqlAlchemyPersistenceAdapter") -> None:
        self.adapter = adapter
        self._context: AbstractContextManager[Connection] | None = None
        self.connection: Connection | None = None

    def __enter__(self) -> "SqlAlchemyTransactionUnitOfWork":
        self._context = self.adapter.engine.begin()
        self.connection = self._context.__enter__()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        traceback,
    ) -> bool:
        if self._context is None:
            return False
        return bool(self._context.__exit__(exc_type, exc, traceback))

    def ensure_inventory_item(self, item: CatalogItem, min_stock_level: int = 100) -> None:
        if self.connection is None:
            raise RuntimeError("Unit of work is not active.")
        self.connection.execute(
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
                    :min_stock_level
                WHERE NOT EXISTS (
                    SELECT 1 FROM inventory WHERE item_name = :item_name
                )
                """
            ),
            {
                "item_name": item.item_name,
                "category": item.category,
                "unit_price": item.unit_price,
                "min_stock_level": min_stock_level,
            },
        )

    def create_transaction(
        self,
        item_name: str,
        transaction_type: TransactionType,
        quantity: int,
        price: float,
        date: str,
    ) -> int:
        if self.connection is None:
            raise RuntimeError("Unit of work is not active.")
        return self.adapter.create_transaction(
            item_name=item_name,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            date=date,
            connection=self.connection,
        )


class SqlAlchemyPersistenceAdapter:
    """SQLite/PostgreSQL-compatible SQLAlchemy implementation of repository ports."""

    def __init__(
        self,
        database_url: str = "sqlite:///beaver_choice.db",
        data_dir: str | Path = ".",
        engine: Engine | None = None,
    ) -> None:
        self.engine = engine or create_engine(database_url)
        self.data_dir = Path(data_dir)

    def initialize(self, seed: int = 137) -> None:
        transactions_schema = pd.DataFrame(
            {
                "id": [],
                "item_name": [],
                "transaction_type": [],
                "units": [],
                "price": [],
                "transaction_date": [],
            }
        )
        transactions_schema.to_sql(
            "transactions",
            self.engine,
            if_exists="replace",
            index=False,
        )

        initial_date = datetime(2025, 1, 1).isoformat()

        quote_requests_df = pd.read_csv(self.data_dir / "quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql(
            "quote_requests",
            self.engine,
            if_exists="replace",
            index=False,
        )

        quotes_df = pd.read_csv(self.data_dir / "quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(
                lambda x: x.get("job_type", "")
            )
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(
                lambda x: x.get("order_size", "")
            )
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(
                lambda x: x.get("event_type", "")
            )

        quotes_df = quotes_df[
            [
                "request_id",
                "total_amount",
                "quote_explanation",
                "order_date",
                "job_type",
                "order_size",
                "event_type",
            ]
        ]
        quotes_df.to_sql("quotes", self.engine, if_exists="replace", index=False)

        inventory_df = generate_sample_inventory(seed=seed)
        initial_transactions = [
            {
                "item_name": None,
                "transaction_type": "sales",
                "units": None,
                "price": 50000.0,
                "transaction_date": initial_date,
            }
        ]
        for _, item in inventory_df.iterrows():
            initial_transactions.append(
                {
                    "item_name": item["item_name"],
                    "transaction_type": "stock_orders",
                    "units": item["current_stock"],
                    "price": item["current_stock"] * item["unit_price"],
                    "transaction_date": initial_date,
                }
            )

        pd.DataFrame(initial_transactions).to_sql(
            "transactions",
            self.engine,
            if_exists="append",
            index=False,
        )
        inventory_df.to_sql("inventory", self.engine, if_exists="replace", index=False)

    def create_transaction(
        self,
        item_name: Optional[str],
        transaction_type: TransactionType,
        quantity: Optional[int],
        price: float,
        date: str | datetime,
        connection: Connection | None = None,
    ) -> int:
        date_str = date.isoformat() if isinstance(date, datetime) else date
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        query = text(
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

        def insert(active_connection: Connection) -> int:
            active_connection.execute(query, params)
            return int(
                active_connection.execute(text("SELECT last_insert_rowid()")).scalar_one()
            )

        if connection is not None:
            return insert(connection)
        with self.engine.begin() as active_connection:
            return insert(active_connection)

    def get_all_inventory(self, as_of_date: str) -> Dict[str, int]:
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
        result = pd.read_sql(query, self.engine, params={"as_of_date": as_of_date})
        return {
            str(row["item_name"]): int(row["stock"])
            for _, row in result.iterrows()
        }

    def get_stock_level(self, item_name: str, as_of_date: str | datetime) -> int:
        date_str = as_of_date.isoformat() if isinstance(as_of_date, datetime) else as_of_date
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
        result = pd.read_sql(
            stock_query,
            self.engine,
            params={"item_name": item_name, "as_of_date": date_str},
        )
        if result.empty:
            return 0
        return int(result.iloc[0]["current_stock"])

    def get_stock_level_frame(
        self,
        item_name: str,
        as_of_date: str | datetime,
    ) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "item_name": item_name,
                    "current_stock": self.get_stock_level(item_name, as_of_date),
                }
            ]
        )

    def get_minimum_stock_level(self, item_name: str) -> int:
        result = pd.read_sql(
            """
            SELECT min_stock_level
            FROM inventory
            WHERE item_name = :item_name
            LIMIT 1
            """,
            self.engine,
            params={"item_name": item_name},
        )
        if result.empty:
            return 100
        return int(result.iloc[0]["min_stock_level"])

    def get_cash_balance(self, as_of_date: str | datetime) -> float:
        date_str = as_of_date.isoformat() if isinstance(as_of_date, datetime) else as_of_date
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            self.engine,
            params={"as_of_date": date_str},
        )
        if transactions.empty:
            return 0.0
        total_sales = transactions.loc[
            transactions["transaction_type"] == "sales",
            "price",
        ].sum()
        total_purchases = transactions.loc[
            transactions["transaction_type"] == "stock_orders",
            "price",
        ].sum()
        return float(total_sales - total_purchases)

    def generate_financial_report(self, as_of_date: str | datetime) -> FinancialReport:
        date_str = as_of_date.isoformat() if isinstance(as_of_date, datetime) else as_of_date
        cash = self.get_cash_balance(date_str)
        inventory_df = pd.read_sql("SELECT * FROM inventory", self.engine)
        inventory_value = 0.0
        for _, item in inventory_df.iterrows():
            stock = self.get_stock_level(item["item_name"], date_str)
            inventory_value += stock * item["unit_price"]
        return financial_report_from_values(date_str, cash, inventory_value)

    def generate_financial_report_dict(self, as_of_date: str | datetime) -> dict:
        date_str = as_of_date.isoformat() if isinstance(as_of_date, datetime) else as_of_date
        report = self.generate_financial_report(date_str)
        inventory_df = pd.read_sql("SELECT * FROM inventory", self.engine)
        inventory_summary = []
        for _, item in inventory_df.iterrows():
            stock = self.get_stock_level(item["item_name"], date_str)
            item_value = stock * item["unit_price"]
            inventory_summary.append(
                {
                    "item_name": item["item_name"],
                    "stock": stock,
                    "unit_price": item["unit_price"],
                    "value": item_value,
                }
            )

        top_sales_query = """
            SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
            FROM transactions
            WHERE transaction_type = 'sales' AND transaction_date <= :date
            GROUP BY item_name
            ORDER BY total_revenue DESC
            LIMIT 5
        """
        top_sales = pd.read_sql(top_sales_query, self.engine, params={"date": date_str})
        return {
            **report.model_dump(),
            "inventory_summary": inventory_summary,
            "top_selling_products": top_sales.to_dict(orient="records"),
        }

    def search_quote_history(self, search_terms: List[str], limit: int = 5) -> List[dict]:
        conditions = []
        params = {}
        for i, term in enumerate(search_terms):
            param_name = f"term_{i}"
            conditions.append(
                f"(LOWER(qr.response) LIKE :{param_name} OR "
                f"LOWER(q.quote_explanation) LIKE :{param_name})"
            )
            params[param_name] = f"%{term.lower()}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"
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
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params)
            return [dict(row._mapping) for row in result]

    def list_transactions(self, as_of_date: Optional[str] = None) -> List[TransactionRecord]:
        params = {}
        where_clause = ""
        if as_of_date:
            where_clause = "WHERE transaction_date <= :as_of_date"
            params["as_of_date"] = as_of_date
        query = f"""
            SELECT
                rowid AS row_id,
                item_name,
                transaction_type,
                units,
                price,
                transaction_date
            FROM transactions
            {where_clause}
            ORDER BY rowid
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(query), params)
            return [
                TransactionRecord(
                    id=int(row._mapping["row_id"]),
                    item_name=row._mapping["item_name"],
                    transaction_type=row._mapping["transaction_type"],
                    units=(
                        int(row._mapping["units"])
                        if row._mapping["units"] is not None
                        else None
                    ),
                    price=float(row._mapping["price"]),
                    transaction_date=row._mapping["transaction_date"],
                )
                for row in rows
            ]

    def count_transactions(self, as_of_date: Optional[str] = None) -> int:
        return len(self.list_transactions(as_of_date))

    def transaction(self) -> SqlAlchemyTransactionUnitOfWork:
        return SqlAlchemyTransactionUnitOfWork(self)

