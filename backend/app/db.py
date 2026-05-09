import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "reml.db"

_CREATE_COMPS = """
CREATE TABLE IF NOT EXISTS comps (
    id                  TEXT PRIMARY KEY,
    address             TEXT NOT NULL,
    submarket           TEXT NOT NULL,
    signed_date         TEXT NOT NULL,
    lease_sf            INTEGER,
    term_months         INTEGER,
    rent_psf_yr_raw     TEXT,
    rent_psf_yr         REAL,
    year_built          INTEGER,
    clear_height_ft     INTEGER,
    source              TEXT,
    notes               TEXT,
    ingestion_status    TEXT NOT NULL,
    drop_reason         TEXT,
    confidence          REAL,
    is_monthly_converted INTEGER DEFAULT 0,
    is_duplicate_of     TEXT
);
"""

_CREATE_INGEST_RUNS = """
CREATE TABLE IF NOT EXISTS ingest_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at        TEXT NOT NULL,
    rows_input    INTEGER,
    rows_used     INTEGER,
    rows_dropped  INTEGER
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(_CREATE_COMPS)
        conn.execute(_CREATE_INGEST_RUNS)
        conn.commit()
