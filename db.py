import os, time
import psycopg
from psycopg.types.json import Jsonb

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://app:app@db:5432/app")


def _conn():
    return psycopg.connect(DATABASE_URL, autocommit=True, connect_timeout=5)


def init_db(retries=30):
    """Wait for Postgres, create schema, and fail interrupted jobs."""
    for _ in range(retries):
        try:
            with _conn() as c:
                c.execute("""CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    result JSONB,
                    created_at TIMESTAMPTZ DEFAULT now())""")
                # A single API process owns these jobs.
                c.execute("UPDATE jobs SET status='failed', result=%s WHERE status='processing'",
                          (Jsonb({"error": "server restarted"}),))
            return
        except psycopg.OperationalError:
            time.sleep(1)
    raise RuntimeError("database is not available")


def create_job(job_id):
    with _conn() as c:
        c.execute("INSERT INTO jobs (job_id, status) VALUES (%s, 'processing')", (job_id,))


def finish_job(job_id, status, result):
    with _conn() as c:
        c.execute("UPDATE jobs SET status=%s, result=%s WHERE job_id=%s AND status='processing'",
                  (status, Jsonb(result), job_id))


def get_job(job_id):
    with _conn() as c:
        return c.execute("SELECT status, result FROM jobs WHERE job_id=%s", (job_id,)).fetchone()
