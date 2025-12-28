"""
Common utilities for data ingestion: normalization, hashing, and helpers.
"""

import hashlib
import json
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def normalize_column_name(col: str) -> str:
    """
    Normalize column names to snake_case, removing spaces and special chars.

    Examples:
        'Employee ID' -> 'employee_id'
        'Expense Date' -> 'expense_date'
        'Amount (USD)' -> 'amount_usd'
    """
    col = col.strip().lower()
    col = re.sub(r'[^\w\s]', '', col)
    col = re.sub(r'\s+', '_', col)
    return col


def normalize_string(value: Any) -> Optional[str]:
    """
    Normalize string values: strip whitespace, convert empty strings to None.
    """
    if value is None or (isinstance(value, float) and value != value):  # NaN check
        return None

    s = str(value).strip()
    return s if s else None


def normalize_date(value: Any) -> Optional[date]:
    """
    Parse date values robustly from Excel serials, datetime objects, or strings.
    Returns None if parsing fails.
    """
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None

    # Handle pandas Timestamp or datetime
    if hasattr(value, 'date'):
        return value.date()

    # Handle date objects directly
    if isinstance(value, date):
        return value

    # Handle Excel serial numbers (days since 1899-12-30)
    if isinstance(value, (int, float)):
        try:
            # Excel serial date: 1 = 1900-01-01 (with leap year bug)
            from datetime import timedelta
            base_date = datetime(1899, 12, 30)
            return (base_date + timedelta(days=float(value))).date()
        except:
            return None

    # Handle string parsing
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        # Try common date formats
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%m-%d-%Y']:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        # Try ISO format parsing
        try:
            return datetime.fromisoformat(value).date()
        except:
            return None

    return None


def normalize_amount(value: Any) -> Optional[Decimal]:
    """
    Parse amount values robustly, handling currency symbols and formatting.

    Examples:
        '$1,234.50' -> Decimal('1234.50')
        '1234.50' -> Decimal('1234.50')
        '(500)' -> Decimal('-500.00')
    """
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None

    # Handle numeric types directly
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value)).quantize(Decimal('0.01'))
        except InvalidOperation:
            return None

    # Handle string parsing
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        # Handle negative numbers in parentheses
        is_negative = False
        if value.startswith('(') and value.endswith(')'):
            is_negative = True
            value = value[1:-1]

        # Remove currency symbols and separators
        value = re.sub(r'[$€£¥,\s]', '', value)

        try:
            amount = Decimal(value).quantize(Decimal('0.01'))
            return -amount if is_negative else amount
        except InvalidOperation:
            return None

    return None


def normalize_currency(value: Any) -> str:
    """
    Normalize currency code to uppercase 3-letter code, default to USD.
    """
    if value is None or (isinstance(value, float) and value != value):
        return 'USD'

    currency = str(value).strip().upper()

    # Map common variations
    currency_map = {
        'DOLLAR': 'USD',
        'DOLLARS': 'USD',
        'US': 'USD',
        'EURO': 'EUR',
        'EUROS': 'EUR',
        'POUND': 'GBP',
        'POUNDS': 'GBP',
    }

    currency = currency_map.get(currency, currency)

    # Validate 3-letter code
    if len(currency) == 3 and currency.isalpha():
        return currency

    return 'USD'


def compute_row_hash(*fields: Any) -> str:
    """
    Compute SHA-256 hash of fields for change detection.
    Handles None values and various data types consistently.
    """
    # Convert all fields to normalized string representation
    parts = []
    for field in fields:
        if field is None:
            parts.append('NULL')
        elif isinstance(field, (date, datetime)):
            parts.append(field.isoformat())
        elif isinstance(field, Decimal):
            parts.append(str(field))
        elif isinstance(field, dict):
            parts.append(json.dumps(field, sort_keys=True))
        else:
            parts.append(str(field))

    # Join with separator and hash
    data = '|'.join(parts)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def safe_json_serialize(obj: Any) -> Any:
    """
    Convert objects to JSON-serializable format.
    Handles datetime, date, Decimal, and other common types.
    """
    if obj is None:
        return None
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_json_serialize(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return str(obj)
    else:
        return obj
