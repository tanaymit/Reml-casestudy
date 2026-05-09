# Reml Insights — Market Rent Engine

Auditable industrial rent estimation. Given a target asset and a noisy stream of
comparable lease transactions, produces a rent estimate with a confidence score and a
transparent adjustment waterfall.

---

## Quick Start

**Two commands:**

```bash
# 1 — Backend (Python 3.10+)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# API runs at http://localhost:8000
# Ingest runs automatically on startup

# 2 — Frontend (Node 18+)
cd frontend
npm install
npm run dev
# UI runs at http://localhost:3000
```

Open **http://localhost:3000** — the page loads `target_asset.json`, calls the API,
and renders the waterfall + comp tables.

---

## Architecture

```
backend/
  app/
    db.py         — SQLite schema + connection
    ingest.py     — CSV load, data-quality decisions, confidence scoring
    estimator.py  — estimate_market_rent() with waterfall reconstruction
    models.py     — Pydantic types (Decimal for money, validated inputs)
    main.py       — FastAPI: POST /api/v1/market-rent/estimate
  seed.py         — standalone ingest script (also runs on API startup)
  requirements.txt

frontend/
  app/page.tsx    — single-page UI
  lib/api.ts      — typed API client

data/
  comps_phx_industrial.csv
  target_asset.json
```

## API

```
POST /api/v1/market-rent/estimate
Content-Type: application/json

{
  "address": "4150 S 51st Ave, Phoenix, AZ 85043",
  "submarket": "Sky Harbor",
  "total_sf": 145000,
  "year_built": 2008,
  "clear_height_ft": 32,
  "as_of": "2025-09-30"
}
```

Returns `RentEstimate` with `point_estimate_psf_yr` (Decimal), `low/high` band,
`confidence`, and the full `waterfall` array. Every step's `after` feeds the next
step's `before`; the final `after` equals the point estimate.

## Data Quality Decisions

See `backend/app/ingest.py` docstring and `NOTES.md` for the full rationale.
Short version:

| Issue | Decision |
|---|---|
| Monthly-quoted rents | Detected via `notes` field + sanity check (< $2.50 annual impossible); multiplied × 12 |
| Undisclosed rents | Dropped; retained in DB with `drop_reason=rent_undisclosed` |
| Duplicates | Same address + date → rents averaged, duplicate marked `drop_reason=duplicate_merged_into:` |
| Deer Valley / Goodyear | Dropped as clearly outside Sky Harbor market |
| Missing height / vintage | Kept; confidence penalized; adjustment skipped for that dimension |
