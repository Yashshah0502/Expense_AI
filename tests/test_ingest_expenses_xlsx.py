"""
Unit and integration tests for XLSX expense ingestion.
"""

import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
import psycopg

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'ingest_sql'))

from ingest_common import (
    normalize_column_name,
    normalize_string,
    normalize_date,
    normalize_amount,
    normalize_currency,
    compute_row_hash,
)
from ingest_expenses_xlsx import (
    map_columns,
    validate_columns,
    normalize_row,
    ingest_xlsx,
)


# Unit tests (no DB required)

class TestNormalizationFunctions:
    """Test pure normalization functions."""

    def test_normalize_column_name(self):
        assert normalize_column_name('Employee ID') == 'employee_id'
        assert normalize_column_name('Expense Date') == 'expense_date'
        assert normalize_column_name('Amount (USD)') == 'amount_usd'
        assert normalize_column_name('  Merchant  ') == 'merchant'

    def test_normalize_string(self):
        assert normalize_string('  test  ') == 'test'
        assert normalize_string('') is None
        assert normalize_string('   ') is None
        assert normalize_string(None) is None
        assert normalize_string(float('nan')) is None

    def test_normalize_date(self):
        # Date object
        assert normalize_date(date(2024, 1, 15)) == date(2024, 1, 15)

        # String formats
        assert normalize_date('2024-01-15') == date(2024, 1, 15)
        assert normalize_date('01/15/2024') == date(2024, 1, 15)

        # Invalid
        assert normalize_date('invalid') is None
        assert normalize_date(None) is None

    def test_normalize_amount(self):
        # Numeric
        assert normalize_amount(1234.50) == Decimal('1234.50')
        assert normalize_amount(1234) == Decimal('1234.00')

        # String with formatting
        assert normalize_amount('$1,234.50') == Decimal('1234.50')
        assert normalize_amount('1234.50') == Decimal('1234.50')

        # Negative in parentheses
        assert normalize_amount('(500)') == Decimal('-500.00')

        # Invalid
        assert normalize_amount('invalid') is None
        assert normalize_amount(None) is None

    def test_normalize_currency(self):
        assert normalize_currency('USD') == 'USD'
        assert normalize_currency('usd') == 'USD'
        assert normalize_currency('EUR') == 'EUR'
        assert normalize_currency('DOLLAR') == 'USD'
        assert normalize_currency(None) == 'USD'
        assert normalize_currency('') == 'USD'

    def test_compute_row_hash(self):
        hash1 = compute_row_hash('org1', 'file.xlsx', 1, 'emp1', 100.50)
        hash2 = compute_row_hash('org1', 'file.xlsx', 1, 'emp1', 100.50)
        hash3 = compute_row_hash('org1', 'file.xlsx', 1, 'emp1', 100.51)

        # Same inputs produce same hash
        assert hash1 == hash2

        # Different inputs produce different hash
        assert hash1 != hash3

        # Hash is hex string
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)


class TestColumnMapping:
    """Test column mapping and validation."""

    def test_map_columns(self):
        df = pd.DataFrame({
            'Employee ID': [1],
            'Expense Date': ['2024-01-15'],
            'Amount (USD)': [100.50],
        })

        df = map_columns(df)

        assert 'employee_id' in df.columns
        assert 'expense_date' in df.columns
        assert 'amount_usd' in df.columns

    def test_validate_columns_success(self):
        df = pd.DataFrame(columns=[
            'employee_id', 'report_id', 'expense_date', 'category',
            'merchant', 'description', 'amount', 'currency', 'receipt_id'
        ])

        # Should not raise
        validate_columns(df)

    def test_validate_columns_missing(self):
        df = pd.DataFrame(columns=['employee_id', 'amount'])

        with pytest.raises(ValueError, match='Missing required columns'):
            validate_columns(df)


class TestRowNormalization:
    """Test row normalization logic."""

    def test_normalize_row(self):
        row = pd.Series({
            'employee_id': 'EMP001',
            'report_id': 'RPT001',
            'expense_date': '2024-01-15',
            'category': 'Travel',
            'merchant': 'Hotel XYZ',
            'description': 'Lodging',
            'amount': '$125.50',
            'currency': 'USD',
            'receipt_id': 'REC001',
        })

        result = normalize_row(row, 'test.xlsx', 2, 'TestOrg')

        assert result['org'] == 'TestOrg'
        assert result['source_file'] == 'test.xlsx'
        assert result['source_row'] == 2
        assert result['employee_id'] == 'EMP001'
        assert result['report_id'] == 'RPT001'
        assert result['expense_date'] == date(2024, 1, 15)
        assert result['category'] == 'Travel'
        assert result['merchant'] == 'Hotel XYZ'
        assert result['description'] == 'Lodging'
        assert result['amount'] == Decimal('125.50')
        assert result['currency'] == 'USD'
        assert result['receipt_id'] == 'REC001'
        assert len(result['row_hash']) == 64


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
class TestXLSXIngestionIntegration:
    """Integration tests for XLSX ingestion."""

    def create_test_xlsx(self, data: list[dict]) -> Path:
        """Create a temporary XLSX file with test data."""
        df = pd.DataFrame(data)

        temp_file = tempfile.NamedTemporaryFile(
            mode='wb',
            suffix='.xlsx',
            delete=False
        )
        temp_path = Path(temp_file.name)

        df.to_excel(temp_path, index=False)

        return temp_path

    def test_ingest_new_rows(self, db_connection):
        """Test ingesting new expense rows."""
        # Create test data
        test_data = [
            {
                'Employee ID': 'EMP001',
                'Report ID': 'RPT001',
                'Expense Date': '2024-01-15',
                'Category': 'Travel',
                'Merchant': 'Hotel XYZ',
                'Description': 'Lodging',
                'Amount': 125.50,
                'Currency': 'USD',
                'Receipt ID': 'REC001',
            },
            {
                'Employee ID': 'EMP002',
                'Report ID': 'RPT002',
                'Expense Date': '2024-01-16',
                'Category': 'Meals',
                'Merchant': 'Restaurant ABC',
                'Description': 'Client dinner',
                'Amount': 85.00,
                'Currency': 'USD',
                'Receipt ID': 'REC002',
            },
            {
                'Employee ID': 'EMP001',
                'Report ID': 'RPT001',
                'Expense Date': '2024-01-17',
                'Category': 'Transport',
                'Merchant': 'Taxi Co',
                'Description': 'Airport transfer',
                'Amount': 45.00,
                'Currency': 'USD',
                'Receipt ID': 'REC003',
            },
        ]

        xlsx_path = self.create_test_xlsx(test_data)

        try:
            # First ingestion
            ingest_xlsx(TEST_DB_URL, 'TestOrg', str(xlsx_path))

            # Verify rows inserted
            with db_connection.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM expenses WHERE org = %s", ('TestOrg',))
                count = cur.fetchone()[0]
                assert count == 3
        finally:
            xlsx_path.unlink()

    def test_ingest_idempotency(self, db_connection):
        """Test that re-ingesting same data doesn't create duplicates."""
        test_data = [
            {
                'Employee ID': 'EMP001',
                'Report ID': 'RPT001',
                'Expense Date': '2024-01-15',
                'Category': 'Travel',
                'Merchant': 'Hotel XYZ',
                'Description': 'Lodging',
                'Amount': 125.50,
                'Currency': 'USD',
                'Receipt ID': 'REC001',
            },
        ]

        xlsx_path = self.create_test_xlsx(test_data)

        try:
            # First ingestion
            ingest_xlsx(TEST_DB_URL, 'TestOrg', str(xlsx_path))

            # Second ingestion (should be idempotent)
            ingest_xlsx(TEST_DB_URL, 'TestOrg', str(xlsx_path))

            # Verify only one row exists
            with db_connection.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM expenses WHERE org = %s", ('TestOrg',))
                count = cur.fetchone()[0]
                assert count == 1
        finally:
            xlsx_path.unlink()

    def test_ingest_update_changed_row(self, db_connection):
        """Test that changing a row updates it properly."""
        test_data_v1 = [
            {
                'Employee ID': 'EMP001',
                'Report ID': 'RPT001',
                'Expense Date': '2024-01-15',
                'Category': 'Travel',
                'Merchant': 'Hotel XYZ',
                'Description': 'Lodging',
                'Amount': 125.50,
                'Currency': 'USD',
                'Receipt ID': 'REC001',
            },
        ]

        xlsx_path = self.create_test_xlsx(test_data_v1)

        try:
            # First ingestion
            ingest_xlsx(TEST_DB_URL, 'TestOrg', str(xlsx_path))

            # Verify initial amount
            with db_connection.cursor() as cur:
                cur.execute(
                    "SELECT amount FROM expenses WHERE org = %s AND source_row = %s",
                    ('TestOrg', 2)
                )
                amount = cur.fetchone()[0]
                assert amount == Decimal('125.50')

            # Modify the data (change amount)
            test_data_v2 = test_data_v1.copy()
            test_data_v2[0] = test_data_v2[0].copy()
            test_data_v2[0]['Amount'] = 150.00

            xlsx_path.unlink()
            xlsx_path = self.create_test_xlsx(test_data_v2)

            # Second ingestion with modified data
            ingest_xlsx(TEST_DB_URL, 'TestOrg', str(xlsx_path))

            # Verify amount was updated
            with db_connection.cursor() as cur:
                cur.execute(
                    "SELECT amount FROM expenses WHERE org = %s AND source_row = %s",
                    ('TestOrg', 2)
                )
                amount = cur.fetchone()[0]
                assert amount == Decimal('150.00')

                # Verify still only one row
                cur.execute("SELECT COUNT(*) FROM expenses WHERE org = %s", ('TestOrg',))
                count = cur.fetchone()[0]
                assert count == 1
        finally:
            if xlsx_path.exists():
                xlsx_path.unlink()
