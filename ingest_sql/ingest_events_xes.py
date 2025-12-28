"""
Ingest process event logs from XES files into PostgreSQL.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import psycopg
from pm4py.objects.log.importer.xes import importer as xes_importer

from ingest_common import compute_row_hash, safe_json_serialize


def extract_case_id(trace) -> Optional[str]:
    """
    Extract case identifier from trace attributes.
    """
    # Try concept:name first, then case:concept:name
    case_id = trace.attributes.get('concept:name')
    if not case_id:
        case_id = trace.attributes.get('case:concept:name')

    if case_id:
        return str(case_id).strip()

    return None


def extract_activity(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract activity name from event.
    """
    # Try concept:name first, then other common keys
    activity = event.get('concept:name')
    if not activity:
        activity = event.get('activity')
    if not activity:
        activity = event.get('Activity')

    if activity:
        return str(activity).strip()

    return None


def extract_timestamp(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract timestamp from event and convert to ISO format string.
    Returns None if no timestamp found.
    """
    timestamp = event.get('time:timestamp')

    if timestamp is None:
        return None

    # Convert datetime to isoformat string
    if hasattr(timestamp, 'isoformat'):
        return timestamp.isoformat()

    return str(timestamp)


def extract_attributes(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract all event attributes as JSON-serializable dict.
    """
    # Convert all attributes to JSON-serializable format
    attributes = {}

    for key, value in event.items():
        try:
            # Use safe serialization for complex types
            attributes[key] = safe_json_serialize(value)
        except Exception:
            # Fallback to string representation
            attributes[key] = str(value)

    return attributes


def compute_event_hash(
    org: str,
    source_file: str,
    case_id: str,
    event_index: int,
    activity: str,
    event_time: Optional[str],
    attributes: Dict[str, Any],
) -> str:
    """
    Compute hash for event change detection.
    """
    # Serialize attributes with sorted keys for consistent hashing
    attrs_json = json.dumps(attributes, sort_keys=True)

    return compute_row_hash(
        org,
        source_file,
        case_id,
        event_index,
        activity,
        event_time or 'NULL',
        attrs_json,
    )


def upsert_events_batch(
    conn: psycopg.Connection,
    rows: list[Dict],
) -> Tuple[int, int]:
    """
    Upsert a batch of event rows using ON CONFLICT with hash-based change detection.
    Returns (rows_written, rows_skipped_unchanged).
    """
    if not rows:
        return 0, 0

    upsert_sql = """
        INSERT INTO expense_events (
            org, source_file, case_id, event_index, activity,
            event_time, attributes, event_hash, created_at
        ) VALUES (
            %(org)s, %(source_file)s, %(case_id)s, %(event_index)s, %(activity)s,
            %(event_time)s, %(attributes)s, %(event_hash)s, now()
        )
        ON CONFLICT (org, source_file, case_id, event_index)
        DO UPDATE SET
            activity = EXCLUDED.activity,
            event_time = EXCLUDED.event_time,
            attributes = EXCLUDED.attributes,
            event_hash = EXCLUDED.event_hash
        WHERE expense_events.event_hash IS DISTINCT FROM EXCLUDED.event_hash
    """

    with conn.cursor() as cur:
        cur.executemany(upsert_sql, rows)
        rows_affected = cur.rowcount

    return rows_affected, 0


def ingest_xes(
    db_url: str,
    org: str,
    xes_path: str,
    timestamp_sort: bool = True,
    show_progress: bool = False,
    batch_size: int = 500,
) -> None:
    """
    Ingest event log from XES file into PostgreSQL.
    """
    xes_path = Path(xes_path).resolve()

    if not xes_path.exists():
        raise FileNotFoundError(f"XES file not found: {xes_path}")

    print(f"Reading XES file: {xes_path}")

    # Configure pm4py parameters
    parameters = {}
    if timestamp_sort:
        parameters['timestamp_sort'] = True
    if show_progress:
        parameters['show_progress_bar'] = True

    # Import XES log
    log = xes_importer.apply(str(xes_path), parameters=parameters)

    print(f"Loaded {len(log)} traces from XES file")

    # Process traces and events
    source_file = xes_path.name
    normalized_events = []
    traces_skipped = 0
    events_skipped = 0

    for trace in log:
        # Extract case identifier
        case_id = extract_case_id(trace)

        if not case_id:
            traces_skipped += 1
            print(f"Warning: Skipping trace without case_id")
            continue

        # Process events in trace
        for event_index, event in enumerate(trace, start=1):
            # Extract activity
            activity = extract_activity(event)

            if not activity:
                events_skipped += 1
                print(f"Warning: Skipping event without activity in case {case_id}")
                continue

            # Extract timestamp (optional)
            event_time = extract_timestamp(event)

            # Extract all attributes
            attributes = extract_attributes(event)

            # Compute hash
            event_hash = compute_event_hash(
                org=org,
                source_file=source_file,
                case_id=case_id,
                event_index=event_index,
                activity=activity,
                event_time=event_time,
                attributes=attributes,
            )

            normalized_events.append({
                'org': org,
                'source_file': source_file,
                'case_id': case_id,
                'event_index': event_index,
                'activity': activity,
                'event_time': event_time,
                'attributes': json.dumps(attributes),
                'event_hash': event_hash,
            })

    print(f"Normalized {len(normalized_events)} events")
    print(f"Traces skipped (no case_id): {traces_skipped}")
    print(f"Events skipped (no activity): {events_skipped}")

    # Connect and upsert
    rows_written = 0

    with psycopg.connect(db_url) as conn:
        # Process in batches
        for i in range(0, len(normalized_events), batch_size):
            batch = normalized_events[i:i + batch_size]
            written, _ = upsert_events_batch(conn, batch)
            rows_written += written
            print(f"Processed batch {i // batch_size + 1}: {written} rows affected")

        conn.commit()

    # Summary
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Traces read:           {len(log)}")
    print(f"Traces skipped:        {traces_skipped}")
    print(f"Events read:           {len(normalized_events) + events_skipped}")
    print(f"Events written/updated: {rows_written}")
    print(f"Events skipped:        {events_skipped}")
    print("=" * 60)


def main():
    """
    CLI entry point for XES ingestion.
    """
    parser = argparse.ArgumentParser(
        description="Ingest XES event log into PostgreSQL"
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
        '--xes-path',
        required=True,
        help='Path to XES file',
    )
    parser.add_argument(
        '--timestamp-sort',
        action='store_true',
        default=True,
        help='Sort events by timestamp (default: True)',
    )
    parser.add_argument(
        '--no-timestamp-sort',
        dest='timestamp_sort',
        action='store_false',
        help='Do not sort events by timestamp',
    )
    parser.add_argument(
        '--show-progress',
        action='store_true',
        default=False,
        help='Show progress bar during import',
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
        ingest_xes(
            db_url=args.db_url,
            org=args.org,
            xes_path=args.xes_path,
            timestamp_sort=args.timestamp_sort,
            show_progress=args.show_progress,
            batch_size=args.batch_size,
        )
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
