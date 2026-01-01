"""
Ingest structured expense data from XLSX files into PostgreSQL.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import psycopg

from common import (
    normalize_column_name,
    normalize_string,
    normalize_date,
    normalize_amount,
    normalize_currency,
    compute_row_hash,
)


REQUIRED_COLUMNS = {
    'employee_id',
    'report_id',
    'expense_date',
    'category',
    'merchant',
    'description',
    'amount',
    'currency',
    'receipt_id',
}


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize DataFrame column names to match expected schema.
    """
    df.columns = [normalize_column_name(col) for col in df.columns]
    return df


def validate_columns(df: pd.DataFrame) -> None:
    """
    Validate that all required columns are present.
    Raises ValueError if any required columns are missing.
    """
    actual_columns = set(df.columns)
    missing = REQUIRED_COLUMNS - actual_columns

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}. "
            f"Available columns: {sorted(actual_columns)}"
        )


def normalize_row(row: pd.Series, source_file: str, source_row: int, org: str) -> Dict:
    """
    Normalize a single row of expense data.
    """
    employee_id = normalize_string(row.get('employee_id'))
    report_id = normalize_string(row.get('report_id'))
    expense_date = normalize_date(row.get('expense_date'))
    category = normalize_string(row.get('category'))
    merchant = normalize_string(row.get('merchant'))
    description = normalize_string(row.get('description'))
    amount = normalize_amount(row.get('amount'))
    currency = normalize_currency(row.get('currency'))
    receipt_id = normalize_string(row.get('receipt_id'))

    # Compute hash from core fields
    row_hash = compute_row_hash(
        org,
        source_file,
        source_row,
        employee_id,
        report_id,
        expense_date,
        category,
        merchant,
        description,
        amount,
        currency,
        receipt_id,
    )

    return {
        'org': org,
        'source_file': source_file,
        'source_row': source_row,
        'employee_id': employee_id,
        'report_id': report_id,
        'expense_date': expense_date,
        'category': category,
        'merchant': merchant,
        'description': description,
        'amount': amount,
        'currency': currency,
        'receipt_id': receipt_id,
        'row_hash': row_hash,
    }


def upsert_expenses_batch(
    conn: psycopg.Connection,
    rows: list[Dict],
) -> Tuple[int, int]:
    """
    Upsert a batch of expense rows using ON CONFLICT with hash-based change detection.
    Returns (rows_written, rows_skipped_unchanged).
    """
    if not rows:
        return 0, 0

    upsert_sql = """
        INSERT INTO expenses (
            org, source_file, source_row, employee_id, report_id,
            expense_date, category, merchant, description, amount,
            currency, receipt_id, row_hash, created_at, updated_at
        ) VALUES (
            %(org)s, %(source_file)s, %(source_row)s, %(employee_id)s, %(report_id)s,
            %(expense_date)s, %(category)s, %(merchant)s, %(description)s, %(amount)s,
            %(currency)s, %(receipt_id)s, %(row_hash)s, now(), now()
        )
        ON CONFLICT (org, source_file, source_row)
        DO UPDATE SET
            employee_id = EXCLUDED.employee_id,
            report_id = EXCLUDED.report_id,
            expense_date = EXCLUDED.expense_date,
            category = EXCLUDED.category,
            merchant = EXCLUDED.merchant,
            description = EXCLUDED.description,
            amount = EXCLUDED.amount,
            currency = EXCLUDED.currency,
            receipt_id = EXCLUDED.receipt_id,
            row_hash = EXCLUDED.row_hash,
            updated_at = now()
        WHERE expenses.row_hash IS DISTINCT FROM EXCLUDED.row_hash
    """

    with conn.cursor() as cur:
        # Execute batch upsert
        cur.executemany(upsert_sql, rows)
        rows_affected = cur.rowcount

    # Count how many were actually updated (hash changed)
    # Note: rowcount includes both inserts and updates
    # For precise counting, we'd need to track before/after, but for simplicity
    # we return total affected and let caller infer
    return rows_affected, 0


def ingest_xlsx(
    db_url: str,
    org: str,
    xlsx_path: str,
    sheet: Optional[str] = None,
    batch_size: int = 500,
) -> None:
    """
    Ingest expense data from XLSX file into PostgreSQL.
    """
    xlsx_path = Path(xlsx_path).resolve()

    if not xlsx_path.exists():
        raise FileNotFoundError(f"XLSX file not found: {xlsx_path}")

    print(f"Reading XLSX file: {xlsx_path}")

    # Read Excel file
    if sheet:
        df = pd.read_excel(xlsx_path, sheet_name=sheet)
    else:
        df = pd.read_excel(xlsx_path)

    print(f"Loaded {len(df)} rows from sheet")

    # Normalize column names
    df = map_columns(df)

    # Validate required columns
    validate_columns(df)

    # Prepare normalized rows
    source_file = xlsx_path.name
    normalized_rows = []

    for idx, row in df.iterrows():
        try:
            # 1-based row index (excluding header)
            source_row = idx + 2  # Excel row number (1-based + header)
            normalized = normalize_row(row, source_file, source_row, org)
            normalized_rows.append(normalized)
        except Exception as e:
            print(f"Warning: Failed to normalize row {idx + 2}: {e}")

    print(f"Normalized {len(normalized_rows)} rows")

    # Connect and upsert
    rows_written = 0
    rows_failed = len(df) - len(normalized_rows)

    with psycopg.connect(db_url) as conn:
        # Process in batches
        for i in range(0, len(normalized_rows), batch_size):
            batch = normalized_rows[i:i + batch_size]
            written, _ = upsert_expenses_batch(conn, batch)
            rows_written += written
            print(f"Processed batch {i // batch_size + 1}: {written} rows affected")

        conn.commit()

    # Summary
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Rows read:             {len(df)}")
    print(f"Rows written/updated:  {rows_written}")
    print(f"Rows failed:           {rows_failed}")
    print("=" * 60)


def main():
    """
    CLI entry point for XLSX ingestion.
    """
    parser = argparse.ArgumentParser(
        description="Ingest expense XLSX data into PostgreSQL"
    )
    parser.add_argument(
        '--db-url',
        default=os.getenv('DATABASE_URL'),
        help='PostgreSQL connection URL (or set DATABASE_URL env var)',
    )
    parser.add_argument(
        '--org',
        default=os.getenv('ORG'),
        help='Organization identifier (or set ORG env var)',
    )
    parser.add_argument(
        '--xlsx-path',
        required=True,
        help='Path to XLSX file',
    )
    parser.add_argument(
        '--sheet',
        default=None,
        help='Sheet name (default: first sheet)',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=500,
        help='Batch size for inserts (default: 500)',
    )

    args = parser.parse_args()

    if not args.db_url:
        print("Error: --db-url or DATABASE_URL environment variable required")
        sys.exit(1)

    if not args.org:
        print("Error: --org or ORG environment variable required")
        sys.exit(1)

    try:
        ingest_xlsx(
            db_url=args.db_url,
            org=args.org,
            xlsx_path=args.xlsx_path,
            sheet=args.sheet,
            batch_size=args.batch_size,
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
