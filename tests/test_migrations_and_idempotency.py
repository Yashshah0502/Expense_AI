"""
Integration tests for migrations and overall idempotency guarantees.
"""

import os
from decimal import Decimal
from pathlib import Path

import pytest
import psycopg


TEST_DB_URL = os.getenv('TEST_DATABASE_URL')


@pytest.fixture(scope='module')
def db_connection():
    """Provide a database connection for migration tests."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    conn = psycopg.connect(TEST_DB_URL)
    yield conn
    conn.close()


@pytest.mark.integration
class TestMigrations:
    """Test migration SQL execution and table structure."""

    def test_migration_creates_tables(self, db_connection):
        """Test that migration creates required tables."""
        # Drop tables if they exist
        db_connection.execute("DROP TABLE IF EXISTS expenses CASCADE")
        db_connection.execute("DROP TABLE IF EXISTS expense_events CASCADE")
        db_connection.commit()

        # Apply migration
        migration_sql = Path(__file__).parent.parent / 'migrations' / '003_create_expense_tables.sql'
        with open(migration_sql) as f:
            db_connection.execute(f.read())
        db_connection.commit()

        # Verify tables exist
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('expenses', 'expense_events')
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]

            assert 'expenses' in tables
            assert 'expense_events' in tables

    def test_expenses_table_structure(self, db_connection):
        """Test expenses table has correct columns and constraints."""
        with db_connection.cursor() as cur:
            # Check columns
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'expenses'
                ORDER BY ordinal_position
            """)
            columns = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

            # Verify key columns exist with correct types
            assert 'expense_id' in columns
            assert 'org' in columns
            assert columns['org'][1] == 'NO'  # NOT NULL
            assert 'source_file' in columns
            assert 'source_row' in columns
            assert 'employee_id' in columns
            assert 'expense_date' in columns
            assert 'amount' in columns
            assert 'row_hash' in columns
            assert columns['row_hash'][1] == 'NO'  # NOT NULL

            # Check unique constraint
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'expenses'
                AND constraint_type = 'UNIQUE'
            """)
            constraints = [row[0] for row in cur.fetchall()]

            assert any('org_source_row' in c for c in constraints)

    def test_expense_events_table_structure(self, db_connection):
        """Test expense_events table has correct columns and constraints."""
        with db_connection.cursor() as cur:
            # Check columns
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'expense_events'
                ORDER BY ordinal_position
            """)
            columns = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

            # Verify key columns exist
            assert 'event_id' in columns
            assert 'org' in columns
            assert columns['org'][1] == 'NO'  # NOT NULL
            assert 'source_file' in columns
            assert 'case_id' in columns
            assert columns['case_id'][1] == 'NO'  # NOT NULL
            assert 'event_index' in columns
            assert 'activity' in columns
            assert columns['activity'][1] == 'NO'  # NOT NULL
            assert 'event_hash' in columns
            assert 'attributes' in columns
            assert columns['attributes'][0] == 'jsonb'  # JSONB type

            # Check unique constraint
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'expense_events'
                AND constraint_type = 'UNIQUE'
            """)
            constraints = [row[0] for row in cur.fetchall()]

            assert any('org_source_case_index' in c for c in constraints)

    def test_indexes_created(self, db_connection):
        """Test that required indexes are created."""
        with db_connection.cursor() as cur:
            # Check expenses indexes
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'expenses'
            """)
            expense_indexes = [row[0] for row in cur.fetchall()]

            assert any('org_date' in idx for idx in expense_indexes)
            assert any('employee_date' in idx for idx in expense_indexes)
            assert any('report' in idx for idx in expense_indexes)

            # Check expense_events indexes
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'expense_events'
            """)
            event_indexes = [row[0] for row in cur.fetchall()]

            assert any('case_time' in idx for idx in event_indexes)
            assert any('activity' in idx for idx in event_indexes)


@pytest.mark.integration
class TestIdempotencyGuarantees:
    """Test idempotency guarantees across multiple ingestion runs."""

    @pytest.fixture(autouse=True)
    def setup_tables(self, db_connection):
        """Ensure tables exist before each test."""
        # Apply migration
        migration_sql = Path(__file__).parent.parent / 'migrations' / '003_create_expense_tables.sql'
        with open(migration_sql) as f:
            db_connection.execute(f.read())
        db_connection.commit()

        # Clean test data
        db_connection.execute("DELETE FROM expenses WHERE org = 'IdempotencyTest'")
        db_connection.execute("DELETE FROM expense_events WHERE org = 'IdempotencyTest'")
        db_connection.commit()

    def test_expenses_no_duplicates_on_reingestion(self, db_connection):
        """Test that re-ingesting same expense data doesn't create duplicates."""
        # Insert test data
        insert_sql = """
            INSERT INTO expenses (
                org, source_file, source_row, employee_id, amount, currency, row_hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (org, source_file, source_row)
            DO UPDATE SET
                employee_id = EXCLUDED.employee_id,
                amount = EXCLUDED.amount,
                row_hash = EXCLUDED.row_hash
            WHERE expenses.row_hash IS DISTINCT FROM EXCLUDED.row_hash
        """

        test_data = [
            ('IdempotencyTest', 'test.xlsx', 1, 'EMP001', Decimal('100.00'), 'USD', 'hash1'),
            ('IdempotencyTest', 'test.xlsx', 2, 'EMP002', Decimal('200.00'), 'USD', 'hash2'),
        ]

        with db_connection.cursor() as cur:
            # First insert
            cur.executemany(insert_sql, test_data)
            db_connection.commit()

            # Count rows
            cur.execute("SELECT COUNT(*) FROM expenses WHERE org = 'IdempotencyTest'")
            count1 = cur.fetchone()[0]
            assert count1 == 2

            # Second insert (same data)
            cur.executemany(insert_sql, test_data)
            db_connection.commit()

            # Count rows (should still be 2)
            cur.execute("SELECT COUNT(*) FROM expenses WHERE org = 'IdempotencyTest'")
            count2 = cur.fetchone()[0]
            assert count2 == 2

    def test_expenses_update_on_hash_change(self, db_connection):
        """Test that expenses update when hash changes."""
        insert_sql = """
            INSERT INTO expenses (
                org, source_file, source_row, employee_id, amount, currency, row_hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (org, source_file, source_row)
            DO UPDATE SET
                employee_id = EXCLUDED.employee_id,
                amount = EXCLUDED.amount,
                row_hash = EXCLUDED.row_hash,
                updated_at = now()
            WHERE expenses.row_hash IS DISTINCT FROM EXCLUDED.row_hash
        """

        with db_connection.cursor() as cur:
            # First insert
            cur.execute(
                insert_sql,
                ('IdempotencyTest', 'test.xlsx', 1, 'EMP001', Decimal('100.00'), 'USD', 'hash1')
            )
            db_connection.commit()

            # Verify initial amount
            cur.execute(
                "SELECT amount FROM expenses WHERE org = 'IdempotencyTest' AND source_row = 1"
            )
            amount1 = cur.fetchone()[0]
            assert amount1 == Decimal('100.00')

            # Update with different hash (different amount)
            cur.execute(
                insert_sql,
                ('IdempotencyTest', 'test.xlsx', 1, 'EMP001', Decimal('150.00'), 'USD', 'hash2')
            )
            db_connection.commit()

            # Verify amount was updated
            cur.execute(
                "SELECT amount, row_hash FROM expenses WHERE org = 'IdempotencyTest' AND source_row = 1"
            )
            row = cur.fetchone()
            assert row[0] == Decimal('150.00')
            assert row[1] == 'hash2'

            # Verify still only one row
            cur.execute("SELECT COUNT(*) FROM expenses WHERE org = 'IdempotencyTest'")
            count = cur.fetchone()[0]
            assert count == 1

    def test_events_no_duplicates_on_reingestion(self, db_connection):
        """Test that re-ingesting same events doesn't create duplicates."""
        insert_sql = """
            INSERT INTO expense_events (
                org, source_file, case_id, event_index, activity, event_hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (org, source_file, case_id, event_index)
            DO UPDATE SET
                activity = EXCLUDED.activity,
                event_hash = EXCLUDED.event_hash
            WHERE expense_events.event_hash IS DISTINCT FROM EXCLUDED.event_hash
        """

        test_data = [
            ('IdempotencyTest', 'test.xes', 'CASE001', 1, 'Submit', 'hash1'),
            ('IdempotencyTest', 'test.xes', 'CASE001', 2, 'Approve', 'hash2'),
        ]

        with db_connection.cursor() as cur:
            # First insert
            cur.executemany(insert_sql, test_data)
            db_connection.commit()

            # Count events
            cur.execute("SELECT COUNT(*) FROM expense_events WHERE org = 'IdempotencyTest'")
            count1 = cur.fetchone()[0]
            assert count1 == 2

            # Second insert (same data)
            cur.executemany(insert_sql, test_data)
            db_connection.commit()

            # Count events (should still be 2)
            cur.execute("SELECT COUNT(*) FROM expense_events WHERE org = 'IdempotencyTest'")
            count2 = cur.fetchone()[0]
            assert count2 == 2

    def test_unique_constraints_prevent_duplicates(self, db_connection):
        """Test that unique constraints prevent duplicate entries."""
        with db_connection.cursor() as cur:
            # Insert expense
            cur.execute("""
                INSERT INTO expenses (
                    org, source_file, source_row, employee_id, amount, currency, row_hash
                ) VALUES (
                    'IdempotencyTest', 'test.xlsx', 1, 'EMP001', 100.00, 'USD', 'hash1'
                )
            """)
            db_connection.commit()

            # Try to insert duplicate (should fail without ON CONFLICT)
            with pytest.raises(psycopg.errors.UniqueViolation):
                cur.execute("""
                    INSERT INTO expenses (
                        org, source_file, source_row, employee_id, amount, currency, row_hash
                    ) VALUES (
                        'IdempotencyTest', 'test.xlsx', 1, 'EMP002', 200.00, 'USD', 'hash2'
                    )
                """)

            db_connection.rollback()
