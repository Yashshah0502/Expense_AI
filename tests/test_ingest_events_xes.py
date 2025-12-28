"""
Unit and integration tests for XES event ingestion.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
import psycopg

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'ingest_sql'))

from ingest_common import compute_row_hash, safe_json_serialize
from ingest_events_xes import (
    extract_case_id,
    extract_activity,
    extract_timestamp,
    extract_attributes,
    compute_event_hash,
    ingest_xes,
)


# Unit tests (no DB required)

class TestExtractionFunctions:
    """Test event extraction functions."""

    def test_extract_case_id(self):
        # Mock trace with concept:name
        class Trace:
            attributes = {'concept:name': 'CASE001'}

        assert extract_case_id(Trace()) == 'CASE001'

        # Mock trace with case:concept:name
        class Trace2:
            attributes = {'case:concept:name': 'CASE002'}

        assert extract_case_id(Trace2()) == 'CASE002'

        # Mock trace without case id
        class Trace3:
            attributes = {}

        assert extract_case_id(Trace3()) is None

    def test_extract_activity(self):
        event1 = {'concept:name': 'Submit'}
        assert extract_activity(event1) == 'Submit'

        event2 = {'activity': 'Approve'}
        assert extract_activity(event2) == 'Approve'

        event3 = {}
        assert extract_activity(event3) is None

    def test_extract_timestamp(self):
        # Datetime object
        dt = datetime(2024, 1, 15, 10, 30, 0)
        event1 = {'time:timestamp': dt}
        assert extract_timestamp(event1) == '2024-01-15T10:30:00'

        # No timestamp
        event2 = {}
        assert extract_timestamp(event2) is None

    def test_extract_attributes(self):
        event = {
            'concept:name': 'Submit',
            'time:timestamp': datetime(2024, 1, 15, 10, 30, 0),
            'org:resource': 'Alice',
            'amount': 125.50,
        }

        attrs = extract_attributes(event)

        assert attrs['concept:name'] == 'Submit'
        assert attrs['time:timestamp'] == '2024-01-15T10:30:00'
        assert attrs['org:resource'] == 'Alice'
        assert attrs['amount'] == 125.50

    def test_compute_event_hash(self):
        hash1 = compute_event_hash(
            'TestOrg', 'test.xes', 'CASE001', 1, 'Submit',
            '2024-01-15T10:30:00', {'key': 'value'}
        )
        hash2 = compute_event_hash(
            'TestOrg', 'test.xes', 'CASE001', 1, 'Submit',
            '2024-01-15T10:30:00', {'key': 'value'}
        )
        hash3 = compute_event_hash(
            'TestOrg', 'test.xes', 'CASE001', 1, 'Approve',
            '2024-01-15T10:30:00', {'key': 'value'}
        )

        # Same inputs produce same hash
        assert hash1 == hash2

        # Different inputs produce different hash
        assert hash1 != hash3


class TestSafeJsonSerialize:
    """Test JSON serialization helper."""

    def test_serialize_datetime(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = safe_json_serialize(dt)
        assert result == '2024-01-15T10:30:00'

    def test_serialize_dict(self):
        data = {
            'timestamp': datetime(2024, 1, 15, 10, 30, 0),
            'amount': 125.50,
            'name': 'Test',
        }
        result = safe_json_serialize(data)

        assert result['timestamp'] == '2024-01-15T10:30:00'
        assert result['amount'] == 125.50
        assert result['name'] == 'Test'

    def test_serialize_list(self):
        data = [datetime(2024, 1, 15), 'test', 123]
        result = safe_json_serialize(data)

        assert result[0] == '2024-01-15'
        assert result[1] == 'test'
        assert result[2] == 123


# Integration tests (require DB)

TEST_DB_URL = os.getenv('TEST_DATABASE_URL')

@pytest.fixture
def db_connection():
    """Provide a database connection for integration tests."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    conn = psycopg.connect(TEST_DB_URL)

    # Apply migration
    migration_sql = Path(__file__).parent.parent / 'migrations' / '003_create_expense_tables.sql'
    with open(migration_sql) as f:
        conn.execute(f.read())
    conn.commit()

    yield conn

    # Cleanup
    conn.execute("DROP TABLE IF EXISTS expenses CASCADE")
    conn.execute("DROP TABLE IF EXISTS expense_events CASCADE")
    conn.commit()
    conn.close()


@pytest.mark.integration
class TestXESIngestionIntegration:
    """Integration tests for XES ingestion."""

    def create_test_xes(self) -> Path:
        """Create a minimal valid XES file with test data."""
        xes_content = """<?xml version="1.0" encoding="UTF-8"?>
<log xes.version="1849.2016" xes.features="nested-attributes" openxes.version="1.0RC7">
  <extension name="Concept" prefix="concept" uri="http://www.xes-standard.org/concept.xesext"/>
  <extension name="Time" prefix="time" uri="http://www.xes-standard.org/time.xesext"/>
  <extension name="Organizational" prefix="org" uri="http://www.xes-standard.org/org.xesext"/>

  <trace>
    <string key="concept:name" value="CASE001"/>

    <event>
      <string key="concept:name" value="Submit"/>
      <date key="time:timestamp" value="2024-01-15T10:00:00.000+00:00"/>
      <string key="org:resource" value="Alice"/>
      <float key="amount" value="125.50"/>
    </event>

    <event>
      <string key="concept:name" value="Approve"/>
      <date key="time:timestamp" value="2024-01-15T14:30:00.000+00:00"/>
      <string key="org:resource" value="Bob"/>
    </event>
  </trace>
</log>
"""

        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.xes',
            delete=False,
            encoding='utf-8'
        )
        temp_path = Path(temp_file.name)
        temp_file.write(xes_content)
        temp_file.close()

        return temp_path

    def test_ingest_new_events(self, db_connection):
        """Test ingesting new events."""
        xes_path = self.create_test_xes()

        try:
            # First ingestion
            ingest_xes(TEST_DB_URL, 'TestOrg', str(xes_path))

            # Verify events inserted
            with db_connection.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM expense_events WHERE org = %s",
                    ('TestOrg',)
                )
                count = cur.fetchone()[0]
                assert count == 2

                # Verify event details
                cur.execute(
                    """
                    SELECT case_id, event_index, activity
                    FROM expense_events
                    WHERE org = %s
                    ORDER BY event_index
                    """,
                    ('TestOrg',)
                )
                events = cur.fetchall()

                assert events[0][0] == 'CASE001'
                assert events[0][1] == 1
                assert events[0][2] == 'Submit'

                assert events[1][0] == 'CASE001'
                assert events[1][1] == 2
                assert events[1][2] == 'Approve'
        finally:
            xes_path.unlink()

    def test_ingest_idempotency(self, db_connection):
        """Test that re-ingesting same XES doesn't create duplicates."""
        xes_path = self.create_test_xes()

        try:
            # First ingestion
            ingest_xes(TEST_DB_URL, 'TestOrg', str(xes_path))

            # Second ingestion (should be idempotent)
            ingest_xes(TEST_DB_URL, 'TestOrg', str(xes_path))

            # Verify still only 2 events
            with db_connection.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM expense_events WHERE org = %s",
                    ('TestOrg',)
                )
                count = cur.fetchone()[0]
                assert count == 2
        finally:
            xes_path.unlink()

    def test_event_attributes_json(self, db_connection):
        """Test that event attributes are stored as valid JSON."""
        xes_path = self.create_test_xes()

        try:
            ingest_xes(TEST_DB_URL, 'TestOrg', str(xes_path))

            # Verify JSON attributes
            with db_connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT attributes
                    FROM expense_events
                    WHERE org = %s AND activity = %s
                    """,
                    ('TestOrg', 'Submit')
                )
                attrs_json = cur.fetchone()[0]

                # Should be valid JSON
                attrs = json.loads(attrs_json)

                assert attrs['concept:name'] == 'Submit'
                assert attrs['org:resource'] == 'Alice'
                assert attrs['amount'] == 125.50
        finally:
            xes_path.unlink()
