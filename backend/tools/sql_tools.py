"""
Safe, read-only SQL query functions for expense data.
All functions use parameterized queries to prevent SQL injection.
All functions enforce hard row limits.
All functions return uniform envelope: {ok: bool, data: ..., warning: str | None}
"""

from datetime import date
from decimal import Decimal
from typing import Optional, Dict, List, Any
import psycopg


# Hard limits to prevent excessive data retrieval
MAX_TOTALS_ROWS = 200
MAX_SAMPLES_ROWS = 50
MAX_TIMELINE_ROWS = 200
MAX_DUPLICATES_ROWS = 50

# Allowlist for GROUP BY to prevent SQL injection
ALLOWED_GROUP_BY = {"category", "merchant", "currency", "employee_id", "report_id"}


def get_expense_totals(
    conn: psycopg.Connection,
    org: str,
    employee_id: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    group_by: str = "category",
) -> Dict[str, Any]:
    """
    Get expense totals grouped by a dimension.

    Args:
        conn: Database connection
        org: Organization name
        employee_id: Optional employee ID filter
        start: Optional start date (inclusive)
        end: Optional end date (inclusive)
        group_by: Dimension to group by (must be in ALLOWED_GROUP_BY)

    Returns:
        {
            "ok": bool,
            "data": [{"group": str, "currency": str, "total": Decimal, "count": int}],
            "warning": str | None
        }
    """
    # Validate group_by to prevent SQL injection
    if group_by not in ALLOWED_GROUP_BY:
        return {
            "ok": False,
            "data": [],
            "warning": f"Invalid group_by: {group_by}. Allowed: {', '.join(ALLOWED_GROUP_BY)}"
        }

    try:
        # Build WHERE conditions
        where_conditions = ["org = %s"]
        params: List[Any] = [org]

        if employee_id:
            where_conditions.append("employee_id = %s")
            params.append(employee_id)

        if start:
            where_conditions.append("expense_date >= %s")
            params.append(start)

        if end:
            where_conditions.append("expense_date <= %s")
            params.append(end)

        where_clause = " AND ".join(where_conditions)

        # Safe to use group_by here since we validated it against allowlist
        query = f"""
            SELECT
                {group_by} as group_name,
                currency,
                SUM(amount) as total,
                COUNT(*) as count
            FROM expenses
            WHERE {where_clause}
            GROUP BY {group_by}, currency
            ORDER BY total DESC
            LIMIT %s
        """

        params.append(MAX_TOTALS_ROWS)

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        data = [
            {
                "group": row[0],
                "currency": row[1],
                "total": row[2],
                "count": row[3],
            }
            for row in rows
        ]

        return {
            "ok": True,
            "data": data,
            "warning": None
        }

    except Exception as e:
        return {
            "ok": False,
            "data": [],
            "warning": f"Database error: {str(e)}"
        }


def get_expense_samples(
    conn: psycopg.Connection,
    org: str,
    employee_id: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Get sample expense rows.

    Args:
        conn: Database connection
        org: Organization name
        employee_id: Optional employee ID filter
        start: Optional start date (inclusive)
        end: Optional end date (inclusive)
        limit: Number of rows to return (clamped to MAX_SAMPLES_ROWS)

    Returns:
        {
            "ok": bool,
            "data": [{"expense_id": int, "employee_id": str, ...}],
            "warning": str | None
        }
    """
    # Clamp limit
    limit = min(limit, MAX_SAMPLES_ROWS)

    try:
        # Build WHERE conditions
        where_conditions = ["org = %s"]
        params: List[Any] = [org]

        if employee_id:
            where_conditions.append("employee_id = %s")
            params.append(employee_id)

        if start:
            where_conditions.append("expense_date >= %s")
            params.append(start)

        if end:
            where_conditions.append("expense_date <= %s")
            params.append(end)

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT
                expense_id,
                employee_id,
                expense_date,
                amount,
                currency,
                category,
                merchant,
                receipt_id,
                report_id,
                description
            FROM expenses
            WHERE {where_clause}
            ORDER BY expense_date DESC, expense_id DESC
            LIMIT %s
        """

        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        data = [
            {
                "expense_id": row[0],
                "employee_id": row[1],
                "expense_date": row[2].isoformat() if row[2] else None,
                "amount": row[3],
                "currency": row[4],
                "category": row[5],
                "merchant": row[6],
                "receipt_id": row[7],
                "report_id": row[8],
                "description": row[9],
            }
            for row in rows
        ]

        return {
            "ok": True,
            "data": data,
            "warning": None
        }

    except Exception as e:
        return {
            "ok": False,
            "data": [],
            "warning": f"Database error: {str(e)}"
        }


def get_case_timeline(
    conn: psycopg.Connection,
    org: str,
    case_id: str,
    limit: int = 200,
) -> Dict[str, Any]:
    """
    Get event timeline for a case.

    Args:
        conn: Database connection
        org: Organization name
        case_id: Case identifier
        limit: Number of events to return (clamped to MAX_TIMELINE_ROWS)

    Returns:
        {
            "ok": bool,
            "data": [{"event_id": int, "case_id": str, "activity": str, ...}],
            "warning": str | None
        }
    """
    # Clamp limit
    limit = min(limit, MAX_TIMELINE_ROWS)

    try:
        query = """
            SELECT
                event_id,
                case_id,
                event_index,
                activity,
                event_time,
                attributes
            FROM expense_events
            WHERE org = %s AND case_id = %s
            ORDER BY event_time NULLS LAST, event_index
            LIMIT %s
        """

        with conn.cursor() as cur:
            cur.execute(query, [org, case_id, limit])
            rows = cur.fetchall()

        data = [
            {
                "event_id": row[0],
                "case_id": row[1],
                "event_index": row[2],
                "activity": row[3],
                "event_time": row[4].isoformat() if row[4] else None,
                "attributes": row[5],
            }
            for row in rows
        ]

        return {
            "ok": True,
            "data": data,
            "warning": None
        }

    except Exception as e:
        return {
            "ok": False,
            "data": [],
            "warning": f"Database error: {str(e)}"
        }


def find_possible_duplicates(
    conn: psycopg.Connection,
    org: str,
    window_days: int = 7,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Find possible duplicate expenses using heuristics.

    Detects duplicates by:
    1. Same receipt_id appearing multiple times
    2. Same (merchant, amount, date) within window_days

    Args:
        conn: Database connection
        org: Organization name
        window_days: Window for detecting duplicates by date proximity
        limit: Number of duplicate groups to return (clamped to MAX_DUPLICATES_ROWS)

    Returns:
        {
            "ok": bool,
            "data": [{"receipt_id": str, "count": int, "total": Decimal, ...}],
            "warning": str | None
        }
    """
    # Clamp limit
    limit = min(limit, MAX_DUPLICATES_ROWS)

    try:
        # Find duplicates by receipt_id
        query_receipt = """
            SELECT
                receipt_id,
                COUNT(*) as count,
                SUM(amount) as total,
                MIN(expense_date) as first_date,
                MAX(expense_date) as last_date,
                'receipt_id' as duplicate_type
            FROM expenses
            WHERE org = %s
                AND receipt_id IS NOT NULL
            GROUP BY receipt_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC, total DESC
            LIMIT %s
        """

        with conn.cursor() as cur:
            cur.execute(query_receipt, [org, limit])
            receipt_dups = cur.fetchall()

        # Find duplicates by (merchant, amount, date window)
        # This is more complex and resource-intensive, so we use a window function
        query_merchant = f"""
            WITH ranked AS (
                SELECT
                    expense_id,
                    merchant,
                    amount,
                    expense_date,
                    COUNT(*) OVER (
                        PARTITION BY merchant, amount
                        ORDER BY expense_date
                        RANGE BETWEEN INTERVAL '{window_days} days' PRECEDING
                                  AND INTERVAL '{window_days} days' FOLLOWING
                    ) as nearby_count
                FROM expenses
                WHERE org = %s
                    AND merchant IS NOT NULL
            )
            SELECT
                merchant,
                amount,
                COUNT(DISTINCT expense_id) as count,
                MIN(expense_date) as first_date,
                MAX(expense_date) as last_date,
                'merchant_amount_date' as duplicate_type
            FROM ranked
            WHERE nearby_count > 1
            GROUP BY merchant, amount
            HAVING COUNT(DISTINCT expense_id) > 1
            ORDER BY count DESC
            LIMIT %s
        """

        with conn.cursor() as cur:
            cur.execute(query_merchant, [org, limit])
            merchant_dups = cur.fetchall()

        # Combine results
        data = []

        for row in receipt_dups:
            data.append({
                "receipt_id": row[0],
                "count": row[1],
                "total": row[2],
                "first_date": row[3].isoformat() if row[3] else None,
                "last_date": row[4].isoformat() if row[4] else None,
                "duplicate_type": row[5],
            })

        for row in merchant_dups:
            data.append({
                "merchant": row[0],
                "amount": row[1],
                "count": row[2],
                "first_date": row[3].isoformat() if row[3] else None,
                "last_date": row[4].isoformat() if row[4] else None,
                "duplicate_type": row[5],
            })

        # Limit total results
        data = data[:limit]

        return {
            "ok": True,
            "data": data,
            "warning": None
        }

    except Exception as e:
        return {
            "ok": False,
            "data": [],
            "warning": f"Database error: {str(e)}"
        }
