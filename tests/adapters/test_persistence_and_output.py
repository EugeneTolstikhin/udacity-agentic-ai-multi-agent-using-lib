import pytest

from beavers_choice.adapters.output_csv import CsvEvaluationOutputAdapter
from beavers_choice.adapters.output_csv import strip_trailing_response_whitespace
from beavers_choice.adapters.persistence_sqlalchemy import SqlAlchemyPersistenceAdapter
from beavers_choice.domain.models import EvaluationRow


def write_seed_csvs(tmp_path):
    (tmp_path / "quote_requests.csv").write_text(
        "mood,job,need_size,event,response\n"
        "calm,office manager,small,meeting,Need A4 paper\n",
        encoding="utf-8",
    )
    (tmp_path / "quotes.csv").write_text(
        "total_amount,quote_explanation,request_metadata\n"
        "10,Prior quote,\"{'job_type': 'office manager', 'order_size': 'small', 'event_type': 'meeting'}\"\n",
        encoding="utf-8",
    )


def test_sqlalchemy_adapter_initializes_sqlite_schema(tmp_path):
    write_seed_csvs(tmp_path)
    adapter = SqlAlchemyPersistenceAdapter(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        data_dir=tmp_path,
    )

    adapter.initialize()

    assert adapter.count_transactions() > 1
    assert adapter.get_cash_balance("2025-04-01") > 0
    assert adapter.search_quote_history(["paper"], limit=1)


def test_sqlalchemy_unit_of_work_commits_and_rolls_back(tmp_path):
    write_seed_csvs(tmp_path)
    adapter = SqlAlchemyPersistenceAdapter(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        data_dir=tmp_path,
    )
    adapter.initialize()
    before = adapter.count_transactions()

    with adapter.transaction() as unit_of_work:
        unit_of_work.create_transaction(
            item_name="A4 paper",
            transaction_type="sales",
            quantity=1,
            price=0.05,
            date="2025-04-01",
        )

    assert adapter.count_transactions() == before + 1

    with pytest.raises(RuntimeError):
        with adapter.transaction() as unit_of_work:
            unit_of_work.create_transaction(
                item_name="A4 paper",
                transaction_type="sales",
                quantity=1,
                price=0.05,
                date="2025-04-01",
            )
            raise RuntimeError("force rollback")

    assert adapter.count_transactions() == before + 1


def test_csv_output_writes_expected_columns_and_summary(tmp_path, capsys):
    output = CsvEvaluationOutputAdapter(tmp_path / "test_results.csv")
    rows = [
        EvaluationRow(
            request_id=1,
            request_date="2025-04-01",
            cash_balance=50010.0,
            inventory_value=100.0,
            response="Order Reference: BC-1",
        ),
        EvaluationRow(
            request_id=2,
            request_date="2025-04-02",
            cash_balance=50010.0,
            inventory_value=100.0,
            response="Unable to fulfill this request.",
        ),
    ]

    output.write_results(rows)

    captured = capsys.readouterr().out
    assert "Saved 2 rows to test_results.csv" in captured
    assert "Cash-balance changes: 1" in captured
    assert "Completed order references: 1" in captured
    assert (tmp_path / "test_results.csv").read_text(encoding="utf-8").startswith(
        "request_id,request_date,cash_balance,inventory_value,response"
    )


def test_csv_output_strips_trailing_response_whitespace():
    assert strip_trailing_response_whitespace("Line one  \nLine two\t") == (
        "Line one\nLine two"
    )
