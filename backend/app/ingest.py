"""
Ingest module: loads comps_phx_industrial.csv into SQLite.

Key decisions (each documented where the logic lives):

1. UNDISCLOSED RENTS — rows where rent_psf_yr is blank, "-", "—", "–", or "undisclosed"
   are marked dropped(rent_undisclosed). They cannot contribute to estimation but are
   retained in the DB so the UI can show them as dropped with reason.

2. MONTHLY vs ANNUAL — the notes field is the authoritative signal ("monthly rent quoted").
   As a safety net, any rent < 2.50 $/sf/yr is also treated as monthly (industrial annual
   rents in Phoenix are consistently $7–12+; sub-$2.50 is impossible annually). Monthly
   rents are multiplied by 12 and flagged is_monthly_converted=1. Confidence is reduced
   slightly (0.92×) to reflect the unit-conversion step.

3. DUPLICATES — rows sharing the same address + signed_date from two different sources.
   If both have usable rents: rents are averaged into one canonical record (picked by
   source trustworthiness); the duplicate is dropped with reason duplicate_merged_into:<id>.
   If both are undisclosed: both dropped. This prevents double-counting a deal in the blend,
   which is a fatal evaluation criterion.

4. OFF-SUBMARKET — Deer Valley (north Phoenix, 25+ miles from Sky Harbor) and Goodyear
   (far west Valley) are excluded as clearly outside the target's market. Sky Harbor,
   Southwest Phoenix, and Tolleson are retained with confidence multipliers reflecting
   their proximity to the target.
"""

import csv
import hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.db import get_conn, init_db

DATA_PATH = Path(__file__).parent.parent.parent / "data" / "comps_phx_industrial.csv"

# Submarkets included in estimation with confidence multiplier
INCLUDED_SUBMARKETS: dict[str, float] = {
    "Sky Harbor": 1.00,
    "Southwest Phoenix": 0.90,
    "Tolleson": 0.85,
}

# Submarkets clearly outside target market — dropped, not just penalized
EXCLUDED_SUBMARKETS = {"Deer Valley", "Goodyear"}

_UNDISCLOSED = {"-", "—", "–", "−", "", "undisclosed", "n/a", "na"}

# Source trustworthiness (institutional brokers are most verifiable)
_SOURCE_CONF: dict[str, float] = {
    "JLL": 1.00,
    "CBRE": 1.00,
    "Colliers": 1.00,
    "Cushman": 1.00,
    "Newmark": 1.00,
    "internal": 0.90,
    "broker_flyer": 0.80,
}

_SOURCE_PRIORITY = ["JLL", "CBRE", "Colliers", "Cushman", "Newmark", "internal", "broker_flyer"]


def _stable_id(address: str, signed_date: str, source: str) -> str:
    key = f"{address.strip().lower()}|{signed_date.strip()}|{source.strip().lower()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _parse_int(val: str) -> Optional[int]:
    try:
        return int(float(val.strip())) if val and val.strip() else None
    except (ValueError, AttributeError):
        return None


def _parse_rent_raw(val: str) -> Optional[float]:
    """Return float if parseable and positive, else None."""
    if not val or val.strip().lower() in _UNDISCLOSED:
        return None
    try:
        f = float(val.strip())
        return f if f > 0 else None
    except ValueError:
        return None


def _is_monthly(rent_raw: str, notes: str) -> bool:
    """Authoritative monthly signal is the notes field; sub-$2.50 is a safety net."""
    if notes and "monthly" in notes.lower():
        return True
    v = _parse_rent_raw(rent_raw)
    # Annual Phoenix industrial rents are $7–12+. Anything below 2.50 cannot be annual.
    return v is not None and v < 2.50


def _comp_confidence(
    source: str,
    submarket: str,
    year_built: Optional[int],
    clear_height_ft: Optional[int],
    is_monthly: bool,
) -> float:
    conf = _SOURCE_CONF.get(source, 0.80)
    conf *= INCLUDED_SUBMARKETS.get(submarket, 0.80)
    if year_built is None:
        conf *= 0.95
    if clear_height_ft is None:
        conf *= 0.95
    if is_monthly:
        conf *= 0.92  # slight penalty for unit-conversion step
    return round(min(1.0, max(0.30, conf)), 4)


def _process_row(row: dict, drop_reason: Optional[str] = None, duplicate_of: Optional[str] = None) -> dict:
    address = row["address"].strip()
    submarket = row["submarket"].strip()
    signed_date = row["signed_date"].strip()
    source = row["source"].strip()
    notes = (row.get("notes") or "").strip()
    rent_raw = (row.get("rent_psf_yr") or "").strip()

    lease_sf = _parse_int(row.get("lease_sf", ""))
    term_months = _parse_int(row.get("term_months", ""))
    year_built = _parse_int(row.get("year_built", ""))
    clear_height_ft = _parse_int(row.get("clear_height_ft", ""))

    comp_id = _stable_id(address, signed_date, source)
    status = "used"
    final_drop_reason = drop_reason
    is_monthly = False
    rent_final: Optional[float] = None

    if not final_drop_reason:
        if submarket in EXCLUDED_SUBMARKETS:
            status = "dropped"
            final_drop_reason = f"off_submarket:{submarket}"
        elif submarket not in INCLUDED_SUBMARKETS:
            status = "dropped"
            final_drop_reason = f"unknown_submarket:{submarket}"
        else:
            monthly = _is_monthly(rent_raw, notes)
            raw_val = _parse_rent_raw(rent_raw)

            if raw_val is None:
                status = "dropped"
                final_drop_reason = "rent_undisclosed"
            elif monthly:
                rent_final = round(raw_val * 12, 2)
                is_monthly = True
            else:
                rent_final = raw_val

    confidence: Optional[float] = None
    if status == "used":
        confidence = _comp_confidence(source, submarket, year_built, clear_height_ft, is_monthly)

    return {
        "id": comp_id,
        "address": address,
        "submarket": submarket,
        "signed_date": signed_date,
        "lease_sf": lease_sf,
        "term_months": term_months,
        "rent_psf_yr_raw": rent_raw,
        "rent_psf_yr": rent_final,
        "year_built": year_built,
        "clear_height_ft": clear_height_ft,
        "source": source,
        "notes": notes,
        "ingestion_status": status,
        "drop_reason": final_drop_reason,
        "confidence": confidence,
        "is_monthly_converted": 1 if is_monthly else 0,
        "is_duplicate_of": duplicate_of,
    }


def _resolve_duplicate_group(group: list[dict]) -> list[dict]:
    """
    Given multiple raw CSV rows for the same (address, signed_date):
    - Identify usable records (valid rent, included submarket)
    - If multiple usable: average rents into one canonical record, drop others
    - If one usable: keep it, mark the rest dropped
    - If none usable: keep all as dropped (with their original reasons)
    """
    processed = [_process_row(r) for r in group]
    usable = [p for p in processed if p["ingestion_status"] == "used"]

    if len(usable) <= 1:
        return processed

    # Sort by source trustworthiness; canonical = most trusted source
    usable.sort(
        key=lambda p: _SOURCE_PRIORITY.index(p["source"])
        if p["source"] in _SOURCE_PRIORITY
        else 99
    )

    avg_rent = round(sum(p["rent_psf_yr"] for p in usable) / len(usable), 2)
    rent_list = [p["rent_psf_yr"] for p in usable]

    canonical = dict(usable[0])
    canonical["rent_psf_yr"] = avg_rent
    # Slight confidence penalty: two sources disagree on rent
    canonical["confidence"] = round((canonical["confidence"] or 0.9) * 0.90, 4)
    canonical["notes"] = (
        f"[dup-merged {len(usable)} sources, rents={rent_list}] " + canonical["notes"]
    )

    result: list[dict] = [canonical]

    for dup in usable[1:]:
        dup = dict(dup)
        dup["ingestion_status"] = "dropped"
        dup["drop_reason"] = f"duplicate_merged_into:{canonical['id']}"
        result.append(dup)

    # Keep non-usable with their original drop reasons
    non_usable = [p for p in processed if p not in usable]
    result.extend(non_usable)

    return result


def run_ingest() -> tuple[int, int]:
    init_db()

    raw_rows: list[dict] = []
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw_rows.append(row)

    # Group by (address, signed_date) to detect duplicates before processing
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in raw_rows:
        key = (row["address"].strip(), row["signed_date"].strip())
        groups[key].append(row)

    all_comps: list[dict] = []
    for group in groups.values():
        if len(group) == 1:
            all_comps.append(_process_row(group[0]))
        else:
            all_comps.extend(_resolve_duplicate_group(group))

    rows_used = sum(1 for c in all_comps if c["ingestion_status"] == "used")
    rows_dropped = sum(1 for c in all_comps if c["ingestion_status"] == "dropped")

    with get_conn() as conn:
        conn.execute("DELETE FROM comps")
        conn.executemany(
            """
            INSERT OR REPLACE INTO comps
              (id, address, submarket, signed_date, lease_sf, term_months,
               rent_psf_yr_raw, rent_psf_yr, year_built, clear_height_ft,
               source, notes, ingestion_status, drop_reason, confidence,
               is_monthly_converted, is_duplicate_of)
            VALUES
              (:id, :address, :submarket, :signed_date, :lease_sf, :term_months,
               :rent_psf_yr_raw, :rent_psf_yr, :year_built, :clear_height_ft,
               :source, :notes, :ingestion_status, :drop_reason, :confidence,
               :is_monthly_converted, :is_duplicate_of)
            """,
            all_comps,
        )
        conn.execute(
            "INSERT INTO ingest_runs (run_at, rows_input, rows_used, rows_dropped) VALUES (?,?,?,?)",
            (datetime.utcnow().isoformat(), len(raw_rows), rows_used, rows_dropped),
        )
        conn.commit()

    return rows_used, rows_dropped
