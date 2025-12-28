"""
Internal debug endpoint for validating SQL tools.
Can be disabled via DEBUG_SQL=false environment variable.
"""

import os
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
import psycopg

from tools.sql_tools import (
    get_expense_totals,
    get_expense_samples,
    get_case_timeline,
    find_possible_duplicates,
)


router = APIRouter()

# Check if debug endpoint is enabled
DEBUG_SQL_ENABLED = os.getenv("DEBUG_SQL", "true").lower() in ("true", "1", "yes")
DB_URL = os.getenv("DATABASE_URL")


@router.get("/debug/sql")
def debug_sql(
    mode: str = Query(..., description="Mode: expenses_totals | expenses_sample | events_timeline | duplicates"),
    org: str = Query(..., description="Organization/university name"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    case_id: Optional[str] = Query(None, description="Case ID (required for events_timeline mode)"),
    start_date: Optional[date] = Query(None, description="Start date for filtering"),
    end_date: Optional[date] = Query(None, description="End date for filtering"),
    group_by: str = Query("category", description="Group by dimension (for expenses_totals)"),
    limit: int = Query(20, description="Number of results to return"),
    window_days: int = Query(7, description="Window in days for duplicate detection"),
):
    """
    Internal debug endpoint for validating SQL tools.

    Modes:
    - expenses_totals: Get expense totals grouped by dimension
    - expenses_sample: Get sample expense rows
    - events_timeline: Get event timeline for a case
    - duplicates: Find possible duplicate expenses

    Can be disabled by setting DEBUG_SQL=false in environment.
    """
    if not DEBUG_SQL_ENABLED:
        raise HTTPException(status_code=404, detail="Debug SQL endpoint is disabled")

    if not DB_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")

    try:
        with psycopg.connect(DB_URL) as conn:
            if mode == "expenses_totals":
                return get_expense_totals(
                    conn=conn,
                    org=org,
                    employee_id=employee_id,
                    start=start_date,
                    end=end_date,
                    group_by=group_by,
                )

            elif mode == "expenses_sample":
                return get_expense_samples(
                    conn=conn,
                    org=org,
                    employee_id=employee_id,
                    start=start_date,
                    end=end_date,
                    limit=limit,
                )

            elif mode == "events_timeline":
                if not case_id:
                    raise HTTPException(
                        status_code=422,
                        detail="case_id is required for events_timeline mode"
                    )
                return get_case_timeline(
                    conn=conn,
                    org=org,
                    case_id=case_id,
                    limit=limit,
                )

            elif mode == "duplicates":
                return find_possible_duplicates(
                    conn=conn,
                    org=org,
                    window_days=window_days,
                    limit=limit,
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown mode: {mode}. Valid modes: expenses_totals, expenses_sample, events_timeline, duplicates"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
