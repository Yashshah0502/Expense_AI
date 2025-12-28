"""
Integration tests for SQL tools.
Tests use TEST_DATABASE_URL and insert synthetic data within transactions.
"""

import os
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path

import pytest
import psycopg


TEST_DB_URL = os.getenv('TEST_DATABASE_URL')


@pytest.fixture(scope='module')
def db_connection():
    """Provide a database connection for SQL tools tests."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    conn = psycopg.connect(TEST_DB_URL)
    yield conn
    conn.close()


@pytest.fixture(scope='module')
def setup_test_data(db_connection):
    """Set up test tables and insert synthetic data."""
    # Ensure tables exist
    migration_sql = Path(__file__).parent.parent / 'migrations' / '003_create_expense_tables.sql'
    with open(migration_sql) as f:
        db_connection.execute(f.read())
    db_connection.commit()

    # Clean test data
    db_connection.execute("DELETE FROM expenses WHERE org = 'SQLToolsTest'")
    db_connection.execute("DELETE FROM expense_events WHERE org = 'SQLToolsTest'")
    db_connection.commit()

    # Insert synthetic expenses
    with db_connection.cursor() as cur:
        cur.execute("""
            INSERT INTO expenses (
                org, source_file, source_row, employee_id, expense_date,
                amount, currency, category, merchant, receipt_id, report_id, row_hash
            ) VALUES
                ('SQLToolsTest', 'test.xlsx', 1, 'EMP001', '2024-01-15', 100.00, 'USD', 'Travel', 'Delta', 'R001', 'RPT001', 'hash1'),
                ('SQLToolsTest', 'test.xlsx', 2, 'EMP001', '2024-01-16', 50.00, 'USD', 'Meals', 'Chipotle', 'R002', 'RPT001', 'hash2'),
                ('SQLToolsTest', 'test.xlsx', 3, 'EMP002', '2024-01-17', 200.00, 'USD', 'Travel', 'United', 'R003', 'RPT002', 'hash3'),
                ('SQLToolsTest', 'test.xlsx', 4, 'EMP002', '2024-01-18', 75.00, 'USD', 'Meals', 'Subway', NULL, 'RPT002', 'hash4'),
                ('SQLToolsTest', 'test.xlsx', 5, 'EMP001', '2024-01-20', 100.00, 'USD', 'Travel', 'Delta', 'R001', 'RPT003', 'hash5')
        """)

        # Insert synthetic events
        cur.execute("""
            INSERT INTO expense_events (
                org, source_file, case_id, event_index, activity, event_time, event_hash, attributes
            ) VALUES
                ('SQLToolsTest', 'test.xes', 'CASE001', 1, 'Submit', '2024-01-15 10:00:00', 'evhash1', '{"employee": "EMP001"}'::jsonb),
                ('SQLToolsTest', 'test.xes', 'CASE001', 2, 'Review', '2024-01-16 14:00:00', 'evhash2', '{"reviewer": "MGR001"}'::jsonb),
                ('SQLToolsTest', 'test.xes', 'CASE001', 3, 'Approve', '2024-01-17 09:00:00', 'evhash3', '{"approver": "CFO001"}'::jsonb),
                ('SQLToolsTest', 'test.xes', 'CASE002', 1, 'Submit', '2024-01-18 11:00:00', 'evhash4', '{"employee": "EMP002"}'::jsonb),
                ('SQLToolsTest', 'test.xes', 'CASE002', 2, 'Reject', '2024-01-19 15:00:00', 'evhash5', '{"reason": "Missing receipt"}'::jsonb)
        """)

    db_connection.commit()
    yield
    # Cleanup
    db_connection.execute("DELETE FROM expenses WHERE org = 'SQLToolsTest'")
    db_connection.execute("DELETE FROM expense_events WHERE org = 'SQLToolsTest'")
    db_connection.commit()


@pytest.mark.integration
class TestGetExpenseTotals:
    """Test get_expense_totals function."""

    def test_totals_by_category(self, db_connection, setup_test_data):
        """Test expense totals grouped by category."""
        from tools.sql_tools import get_expense_totals

        result = get_expense_totals(db_connection, org="SQLToolsTest", group_by="category")

        assert result["ok"] is True
        assert result["warning"] is None
        assert len(result["data"]) == 2  # Travel and Meals

        # Check Travel category
        travel = next((r for r in result["data"] if r["group"] == "Travel"), None)
        assert travel is not None
        assert travel["currency"] == "USD"
        assert travel["total"] == Decimal("400.00")  # 100 + 200 + 100
        assert travel["count"] == 3

        # Check Meals category
        meals = next((r for r in result["data"] if r["group"] == "Meals"), None)
        assert meals is not None
        assert meals["total"] == Decimal("125.00")  # 50 + 75
        assert meals["count"] == 2

    def test_totals_by_employee(self, db_connection, setup_test_data):
        """Test expense totals grouped by employee_id."""
        from tools.sql_tools import get_expense_totals

        result = get_expense_totals(db_connection, org="SQLToolsTest", group_by="employee_id")

        assert result["ok"] is True
        assert len(result["data"]) == 2

        emp001 = next((r for r in result["data"] if r["group"] == "EMP001"), None)
        assert emp001 is not None
        assert emp001["total"] == Decimal("250.00")  # 100 + 50 + 100
        assert emp001["count"] == 3

    def test_totals_filter_by_employee(self, db_connection, setup_test_data):
        """Test filtering totals by specific employee."""
        from tools.sql_tools import get_expense_totals

        result = get_expense_totals(
            db_connection,
            org="SQLToolsTest",
            employee_id="EMP001",
            group_by="category"
        )

        assert result["ok"] is True
        assert len(result["data"]) == 2  # Travel and Meals for EMP001

        travel = next((r for r in result["data"] if r["group"] == "Travel"), None)
        assert travel["total"] == Decimal("200.00")  # 100 + 100

    def test_totals_date_range(self, db_connection, setup_test_data):
        """Test filtering by date range."""
        from tools.sql_tools import get_expense_totals

        result = get_expense_totals(
            db_connection,
            org="SQLToolsTest",
            start=date(2024, 1, 16),
            end=date(2024, 1, 18),
            group_by="category"
        )

        assert result["ok"] is True
        # Should only include expenses from 2024-01-16 to 2024-01-18
        total_amount = sum(r["total"] for r in result["data"])
        assert total_amount == Decimal("325.00")  # 50 + 200 + 75

    def test_totals_invalid_group_by(self, db_connection, setup_test_data):
        """Test that invalid group_by raises error."""
        from tools.sql_tools import get_expense_totals

        result = get_expense_totals(
            db_connection,
            org="SQLToolsTest",
            group_by="malicious_column; DROP TABLE expenses--"
        )

        assert result["ok"] is False
        assert "Invalid group_by" in result["warning"]

    def test_totals_limit_clamped(self, db_connection, setup_test_data):
        """Test that result count is clamped to MAX_TOTALS_ROWS."""
        from tools.sql_tools import get_expense_totals, MAX_TOTALS_ROWS

        # Even with many results, should not exceed MAX_TOTALS_ROWS
        result = get_expense_totals(db_connection, org="SQLToolsTest", group_by="category")

        assert result["ok"] is True
        assert len(result["data"]) <= MAX_TOTALS_ROWS


@pytest.mark.integration
class TestGetExpenseSamples:
    """Test get_expense_samples function."""

    def test_samples_basic(self, db_connection, setup_test_data):
        """Test basic expense samples retrieval."""
        from tools.sql_tools import get_expense_samples

        result = get_expense_samples(db_connection, org="SQLToolsTest", limit=3)

        assert result["ok"] is True
        assert result["warning"] is None
        assert len(result["data"]) == 3

        # Check structure
        sample = result["data"][0]
        assert "expense_id" in sample
        assert "employee_id" in sample
        assert "expense_date" in sample
        assert "amount" in sample
        assert "currency" in sample
        assert "category" in sample

    def test_samples_filter_by_employee(self, db_connection, setup_test_data):
        """Test filtering samples by employee."""
        from tools.sql_tools import get_expense_samples

        result = get_expense_samples(
            db_connection,
            org="SQLToolsTest",
            employee_id="EMP001"
        )

        assert result["ok"] is True
        assert all(r["employee_id"] == "EMP001" for r in result["data"])
        assert len(result["data"]) == 3

    def test_samples_date_range(self, db_connection, setup_test_data):
        """Test filtering samples by date range."""
        from tools.sql_tools import get_expense_samples

        result = get_expense_samples(
            db_connection,
            org="SQLToolsTest",
            start=date(2024, 1, 17),
            end=date(2024, 1, 18)
        )

        assert result["ok"] is True
        assert len(result["data"]) == 2  # Only expenses on 2024-01-17 and 2024-01-18

    def test_samples_limit_clamped(self, db_connection, setup_test_data):
        """Test that limit is clamped to MAX_SAMPLES_ROWS."""
        from tools.sql_tools import get_expense_samples, MAX_SAMPLES_ROWS

        result = get_expense_samples(
            db_connection,
            org="SQLToolsTest",
            limit=999  # Request more than max
        )

        assert result["ok"] is True
        assert len(result["data"]) <= MAX_SAMPLES_ROWS


@pytest.mark.integration
class TestGetCaseTimeline:
    """Test get_case_timeline function."""

    def test_timeline_basic(self, db_connection, setup_test_data):
        """Test basic case timeline retrieval."""
        from tools.sql_tools import get_case_timeline

        result = get_case_timeline(db_connection, org="SQLToolsTest", case_id="CASE001")

        assert result["ok"] is True
        assert result["warning"] is None
        assert len(result["data"]) == 3

        # Verify order (by event_time, event_index)
        events = result["data"]
        assert events[0]["activity"] == "Submit"
        assert events[1]["activity"] == "Review"
        assert events[2]["activity"] == "Approve"

        # Check structure
        event = events[0]
        assert "event_id" in event
        assert "case_id" in event
        assert event["case_id"] == "CASE001"
        assert "event_index" in event
        assert "activity" in event
        assert "event_time" in event

    def test_timeline_nonexistent_case(self, db_connection, setup_test_data):
        """Test timeline for nonexistent case."""
        from tools.sql_tools import get_case_timeline

        result = get_case_timeline(
            db_connection,
            org="SQLToolsTest",
            case_id="NONEXISTENT"
        )

        assert result["ok"] is True
        assert len(result["data"]) == 0

    def test_timeline_limit_clamped(self, db_connection, setup_test_data):
        """Test that limit is clamped to MAX_TIMELINE_ROWS."""
        from tools.sql_tools import get_case_timeline, MAX_TIMELINE_ROWS

        result = get_case_timeline(
            db_connection,
            org="SQLToolsTest",
            case_id="CASE001",
            limit=999
        )

        assert result["ok"] is True
        assert len(result["data"]) <= MAX_TIMELINE_ROWS


@pytest.mark.integration
class TestFindPossibleDuplicates:
    """Test find_possible_duplicates function."""

    def test_duplicates_by_receipt_id(self, db_connection, setup_test_data):
        """Test finding duplicates by receipt_id."""
        from tools.sql_tools import find_possible_duplicates

        result = find_possible_duplicates(db_connection, org="SQLToolsTest")

        assert result["ok"] is True

        # Should find R001 as duplicate (appears twice)
        r001_group = next((g for g in result["data"] if g.get("receipt_id") == "R001"), None)
        assert r001_group is not None
        assert r001_group["count"] == 2
        assert r001_group["total"] == Decimal("200.00")

    def test_duplicates_by_merchant_amount_date(self, db_connection, setup_test_data):
        """Test finding duplicates by merchant/amount/date within window."""
        from tools.sql_tools import find_possible_duplicates

        # With window_days=7, should find potential duplicates
        result = find_possible_duplicates(
            db_connection,
            org="SQLToolsTest",
            window_days=7
        )

        assert result["ok"] is True
        # At minimum, should find receipt_id duplicates
        assert len(result["data"]) >= 1

    def test_duplicates_limit_clamped(self, db_connection, setup_test_data):
        """Test that limit is clamped to MAX_DUPLICATES_ROWS."""
        from tools.sql_tools import find_possible_duplicates, MAX_DUPLICATES_ROWS

        result = find_possible_duplicates(
            db_connection,
            org="SQLToolsTest",
            limit=999
        )

        assert result["ok"] is True
        assert len(result["data"]) <= MAX_DUPLICATES_ROWS


@pytest.mark.integration
class TestSQLInjectionPrevention:
    """Test that SQL tools are protected against injection attacks."""

    def test_org_parameter_safe(self, db_connection, setup_test_data):
        """Test that org parameter uses parameterized query."""
        from tools.sql_tools import get_expense_totals

        # Attempt SQL injection via org parameter
        result = get_expense_totals(
            db_connection,
            org="SQLToolsTest'; DROP TABLE expenses--",
            group_by="category"
        )

        # Should safely return no results (org doesn't exist)
        assert result["ok"] is True
        assert len(result["data"]) == 0

        # Verify table still exists
        with db_connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM expenses WHERE org = 'SQLToolsTest'")
            count = cur.fetchone()[0]
            assert count == 5  # All test rows still exist

    def test_group_by_allowlist(self, db_connection, setup_test_data):
        """Test that group_by rejects values not in allowlist."""
        from tools.sql_tools import get_expense_totals

        result = get_expense_totals(
            db_connection,
            org="SQLToolsTest",
            group_by="1; DELETE FROM expenses WHERE 1=1--"
        )

        assert result["ok"] is False
        assert "Invalid group_by" in result["warning"]

        # Verify no data was deleted
        with db_connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM expenses WHERE org = 'SQLToolsTest'")
            count = cur.fetchone()[0]
            assert count == 5
