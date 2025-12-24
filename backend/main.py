import os
from fastapi import FastAPI
from dotenv import load_dotenv
import psycopg

# Loads backend/.env into environment vars for local dev
load_dotenv()

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db-health")
def db_health():
    if not DATABASE_URL:
        return {"status": "error", "detail": "DATABASE_URL is missing"}

    # Simple, safe connectivity check
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            val = cur.fetchone()[0]

    return {"status": "ok", "db": val}
