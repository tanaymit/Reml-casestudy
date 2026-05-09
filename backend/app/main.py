from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.estimator import estimate_market_rent
from app.ingest import run_ingest
from app.models import RentEstimate, TargetAsset

app = FastAPI(title="Reml Market Rent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _seed() -> None:
    """Auto-ingest on startup so the API is always ready without a separate seed step."""
    run_ingest()


@app.post("/api/v1/market-rent/estimate", response_model=RentEstimate)
def market_rent_estimate(target: TargetAsset) -> RentEstimate:
    try:
        return estimate_market_rent(target)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/v1/ingest", summary="Re-run ingest (idempotent)")
def trigger_ingest() -> dict:
    used, dropped = run_ingest()
    return {"rows_used": used, "rows_dropped": dropped}


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
