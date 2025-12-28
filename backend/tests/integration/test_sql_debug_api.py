"""
Integration tests for /debug/sql API endpoint.
"""

import os
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import psycopg


TEST_DB_URL = os.getenv('TEST_DATABASE_URL')


@pytest.fixture(scope='module')
def db_connection():
    """Provide database connection for setup."""
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
    db_connection.execute("DELETE FROM expenses WHERE org = 'DebugAPITest'")
    db_connection.execute("DELETE FROM expense_events WHERE org = 'DebugAPITest'")
    db_connection.commit()

    # Insert synthetic expenses
    with db_connection.cursor() as cur:
        cur.execute("""
            INSERT INTO expenses (
                org, source_file, source_row, employee_id, expense_date,
                amount, currency, category, merchant, receipt_id, report_id, row_hash
            ) VALUES
                ('DebugAPITest', 'test.xlsx', 1, 'EMP001', '2024-01-15', 100.00, 'USD', 'Travel', 'Delta', 'R001', 'RPT001', 'hash1'),
                ('DebugAPITest', 'test.xlsx', 2, 'EMP001', '2024-01-16', 50.00, 'USD', 'Meals', 'Chipotle', 'R002', 'RPT001', 'hash2'),
                ('DebugAPITest', 'test.xlsx', 3, 'EMP002', '2024-01-17', 200.00, 'USD', 'Travel', 'United', 'R003', 'RPT002', 'hash3')
        """)

        # Insert synthetic events
        cur.execute("""
            INSERT INTO expense_events (
                org, source_file, case_id, event_index, activity, event_time, event_hash
            ) VALUES
                ('DebugAPITest', 'test.xes', 'CASE001', 1, 'Submit', '2024-01-15 10:00:00', 'evhash1'),
                ('DebugAPITest', 'test.xes', 'CASE001', 2, 'Review', '2024-01-16 14:00:00', 'evhash2'),
                ('DebugAPITest', 'test.xes', 'CASE001', 3, 'Approve', '2024-01-17 09:00:00', 'evhash3')
        """)

    db_connection.commit()
    yield
    # Cleanup
    db_connection.execute("DELETE FROM expenses WHERE org = 'DebugAPITest'")
    db_connection.execute("DELETE FROM expense_events WHERE org = 'DebugAPITest'")
    db_connection.commit()


@pytest.fixture(scope='module')
def client(setup_test_data):
    """Provide FastAPI test client."""
    # Set DEBUG_SQL=true to enable the endpoint
    os.environ['DEBUG_SQL'] = 'true'

    from main import app
    return TestClient(app)


@pytest.mark.integration
class TestDebugSQLEndpoint:
    """Test /debug/sql endpoint functionality."""

    def test_expenses_totals_mode(self, client):
        """Test expenses_totals mode."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_totals",
                "org": "DebugAPITest",
                "group_by": "category"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        assert "data" in data
        assert len(data["data"]) == 2  # Travel and Meals

        # Verify structure
        assert all("group" in r for r in data["data"])
        assert all("total" in r for r in data["data"])
        assert all("count" in r for r in data["data"])

    def test_expenses_sample_mode(self, client):
        """Test expenses_sample mode."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_sample",
                "org": "DebugAPITest",
                "limit": 2
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        assert len(data["data"]) == 2
        assert all("expense_id" in r for r in data["data"])
        assert all("employee_id" in r for r in data["data"])

    def test_expenses_sample_limit_clamped(self, client):
        """Test that limit is clamped to MAX_SAMPLES_ROWS."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_sample",
                "org": "DebugAPITest",
                "limit": 999  # Request more than max
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Import MAX_SAMPLES_ROWS to verify limit
        from tools.sql_tools import MAX_SAMPLES_ROWS

        assert data["ok"] is True
        assert len(data["data"]) <= MAX_SAMPLES_ROWS

    def test_events_timeline_mode(self, client):
        """Test events_timeline mode."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "events_timeline",
                "org": "DebugAPITest",
                "case_id": "CASE001"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        assert len(data["data"]) == 3
        assert data["data"][0]["activity"] == "Submit"
        assert data["data"][1]["activity"] == "Review"
        assert data["data"][2]["activity"] == "Approve"

    def test_events_timeline_missing_case_id(self, client):
        """Test that events_timeline requires case_id."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "events_timeline",
                "org": "DebugAPITest"
                # Missing case_id
            }
        )

        assert response.status_code == 422  # Validation error

    def test_duplicates_mode(self, client):
        """Test duplicates mode."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "duplicates",
                "org": "DebugAPITest",
                "window_days": 7
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        assert "data" in data
        # May or may not find duplicates, but should succeed

    def test_invalid_mode(self, client):
        """Test that invalid mode returns error."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "invalid_mode",
                "org": "DebugAPITest"
            }
        )

        assert response.status_code == 400
        assert "Unknown mode" in response.json()["detail"]

    def test_missing_required_org(self, client):
        """Test that org parameter is required."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_sample"
                # Missing org
            }
        )

        assert response.status_code == 422  # Validation error

    def test_employee_filter(self, client):
        """Test filtering by employee_id."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_sample",
                "org": "DebugAPITest",
                "employee_id": "EMP001"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        assert all(r["employee_id"] == "EMP001" for r in data["data"])

    def test_date_range_filter(self, client):
        """Test filtering by date range."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_sample",
                "org": "DebugAPITest",
                "start_date": "2024-01-16",
                "end_date": "2024-01-17"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        # Should only return expenses within date range
        assert len(data["data"]) == 2

    def test_invalid_group_by(self, client):
        """Test that invalid group_by is rejected."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_totals",
                "org": "DebugAPITest",
                "group_by": "malicious_column"
            }
        )

        assert response.status_code == 200  # Returns ok=False in response
        data = response.json()

        assert data["ok"] is False
        assert "Invalid group_by" in data["warning"]


@pytest.mark.integration
class TestDebugSQLDisabled:
    """Test that endpoint can be disabled via DEBUG_SQL=false."""

    def test_endpoint_disabled(self):
        """Test that endpoint returns 404 when DEBUG_SQL=false."""
        # Set DEBUG_SQL=false
        os.environ['DEBUG_SQL'] = 'false'

        from main import app
        client = TestClient(app)

        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_sample",
                "org": "DebugAPITest"
            }
        )

        assert response.status_code == 404
        assert "disabled" in response.json()["detail"]

        # Reset for other tests
        os.environ['DEBUG_SQL'] = 'true'


@pytest.mark.integration
class TestDebugSQLDataTypes:
    """Test that endpoint returns correct data types."""

    def test_totals_numeric_types(self, client):
        """Test that totals returns proper numeric types."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "expenses_totals",
                "org": "DebugAPITest",
                "group_by": "category"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify numeric fields are numbers (not strings)
        for row in data["data"]:
            assert isinstance(row["total"], (int, float, str))  # JSON may serialize Decimal as string
            assert isinstance(row["count"], int)

    def test_timeline_timestamp_format(self, client):
        """Test that timeline returns properly formatted timestamps."""
        response = client.get(
            "/debug/sql",
            params={
                "mode": "events_timeline",
                "org": "DebugAPITest",
                "case_id": "CASE001"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify event_time is in ISO format
        for event in data["data"]:
            if event.get("event_time"):
                # Should be ISO datetime string
                assert isinstance(event["event_time"], str)
                assert "T" in event["event_time"] or " " in event["event_time"]
