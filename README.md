# Reml Insights - Market Rent Engine

Auditable industrial rent estimation. Give it a target asset and a noisy stream of comparable lease transactions, and it produces a rent estimate with a confidence score and a transparent adjustment waterfall you can trace line by line.

## Quick Start

Two commands, two terminals.

```bash
# Backend (Python 3.10+)
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
# API at http://localhost:8000
# Ingest runs automatically on startup, no separate step needed
```

```bash
# Frontend (Node 18+)
cd frontend
npm install
npm run dev
# UI at http://localhost:3000
```

Open http://localhost:3000. The page loads target_asset.json, calls the API, and renders the waterfall and comp tables.

## Architecture

```
backend/
  app/
    db.py         - SQLite schema and connection
    ingest.py     - CSV load, data quality decisions, confidence scoring
    estimator.py  - estimate_market_rent() with waterfall reconstruction
    models.py     - Pydantic types (Decimal for money, validated inputs)
    main.py       - FastAPI: POST /api/v1/market-rent/estimate
  seed.py         - standalone ingest script (also runs on API startup)
  requirements.txt

frontend/
  app/page.tsx    - single-page UI
  lib/api.ts      - typed API client

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

Returns a RentEstimate with point_estimate_psf_yr (Decimal, not float), a low/high band, confidence, and the full waterfall array. Every step's after feeds the next step's before. The final after equals the point estimate. This is not a rounding coincidence.

## Data Quality Decisions

Full rationale is in backend/app/ingest.py and NOTES.md. Short version:

| Issue | Decision |
|---|---|
| Monthly-quoted rents | Detected via notes field plus a sub-$2.50 sanity check; multiplied x 12 before anything else touches them |
| Undisclosed rents | Dropped, retained in DB with drop_reason=rent_undisclosed |
| Duplicates | Same address and date gets rents averaged; secondary record marked drop_reason=duplicate_merged_into |
| Deer Valley and Goodyear | Dropped, clearly outside Sky Harbor market |
| Missing height or vintage | Kept, confidence penalized, adjustment skipped for that dimension |
