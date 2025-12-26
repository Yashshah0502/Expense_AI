#!/usr/bin/env python
"""Quick database check script"""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

print(f"DATABASE_URL: {db_url[:50]}...")

try:
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM policy_chunks;")
            count = cur.fetchone()[0]
            print(f"✓ Database connected")
            print(f"✓ policy_chunks table has {count} rows")

            # Check sample data
            cur.execute("SELECT DISTINCT org FROM policy_chunks LIMIT 10;")
            orgs = [row[0] for row in cur.fetchall()]
            print(f"✓ Organizations in database: {', '.join(orgs)}")

            cur.execute("SELECT DISTINCT policy_type FROM policy_chunks WHERE policy_type IS NOT NULL LIMIT 10;")
            types = [row[0] for row in cur.fetchall()]
            print(f"✓ Policy types in database: {', '.join(types) if types else 'None'}")

except Exception as e:
    print(f"✗ Database error: {e}")
