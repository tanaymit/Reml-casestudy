"""
Market Rent Estimation Engine

Waterfall order (justified):
  1. Time    — normalize all comp rents to the as_of date before any physical comparison.
               Temporal noise must be removed first so size/height/vintage deltas reflect
               property attributes, not market-cycle drift.
  2. Size    — dominant pricing factor for industrial. Larger spaces trade at lower $/SF;
               the comp pool's average size rarely matches the target exactly.
  3. Clear height — functional premium. A 32-ft building is not merely "different" from a
               24-ft building; it commands a structural premium (higher-bay logistics users,
               rack stacking, modern 3PL). This is the most operationally meaningful
               attribute after size.
  4. Vintage — building age affects mechanical systems, dock efficiency, and obsolescence
               risk but is less deterministic than height for industrial rent.

Reconstruction guarantee:
  waterfall[0].before  == base_rent
  waterfall[-1].after  == point_estimate_psf_yr
  each step: after == before + delta  (verified by _step helper)

Assumptions declared:
  - Time ramp: 3% per year flat (conservative; Phoenix industrial grew 5–8% YoY in 2022–23,
    moderating to 2–4% in 2024–25; 3% is a defensible through-cycle rate).
  - Size elasticity: 1.5% per 50,000 SF difference (industry range 1–2%).
  - Clear height premium: 0.6% per foot vs target's 32 ft (industry range 0.5–1.0%/ft).
  - Vintage premium: 0.35% per year newer (industry range 0.3–0.5%/yr).
"""

from __future__ import annotations

import statistics
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app.db import get_conn
from app.models import CompRecord, RentEstimate, TargetAsset, WaterfallStep

# Declared adjustment parameters
TIME_ANNUAL_RATE = Decimal("0.03")       # 3% annual rent appreciation
SIZE_RATE_PER_50K_SF = Decimal("0.015")  # 1.5% per 50,000 SF size difference
HEIGHT_RATE_PER_FT = Decimal("0.006")    # 0.6% per foot of clear height
VINTAGE_RATE_PER_YR = Decimal("0.0035") # 0.35% per year of vintage difference

_QUANT = Decimal("0.01")
_QUANT4 = Decimal("0.0001")


def _d(v: float | int | str) -> Decimal:
    return Decimal(str(v))


def _q(v: Decimal) -> Decimal:
    return v.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _step(name: str, before: Decimal, after: Decimal, rationale: str) -> WaterfallStep:
    delta = _q(after - before)
    pct = (delta / before * 100).quantize(_QUANT4, rounding=ROUND_HALF_UP) if before else Decimal("0")
    return WaterfallStep(
        step=name,
        before=_q(before),
        after=_q(after),
        delta=delta,
        delta_pct=pct,
        rationale=rationale,
    )


def _fetch_comps() -> tuple[list[CompRecord], list[CompRecord]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM comps ORDER BY signed_date DESC").fetchall()

    used, dropped = [], []
    for r in rows:
        rec = CompRecord(
            id=r["id"],
            address=r["address"],
            submarket=r["submarket"],
            signed_date=r["signed_date"],
            lease_sf=r["lease_sf"],
            rent_psf_yr=_d(r["rent_psf_yr"]) if r["rent_psf_yr"] is not None else None,
            year_built=r["year_built"],
            clear_height_ft=r["clear_height_ft"],
            source=r["source"],
            confidence=r["confidence"],
            status=r["ingestion_status"],
            drop_reason=r["drop_reason"],
            is_monthly_converted=bool(r["is_monthly_converted"]),
        )
        if r["ingestion_status"] == "used":
            used.append(rec)
        else:
            dropped.append(rec)

    return used, dropped


def _weighted_avg(values: list[float], weights: list[float]) -> float:
    total_w = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total_w


def _overall_confidence(
    used: list[CompRecord],
    avg_conf: float,
    cv: float,
    sky_harbor_count: int,
) -> Decimal:
    conf = avg_conf

    # Reward a solid Sky Harbor count
    if sky_harbor_count >= 20:
        conf = min(1.0, conf + 0.05)
    elif sky_harbor_count < 10:
        conf *= 0.90

    # Penalize high spread (coefficient of variation)
    if cv > 0.20:
        conf *= 0.85
    elif cv > 0.12:
        conf *= 0.93

    # Penalize small pool
    if len(used) < 10:
        conf *= 0.80

    return _q(Decimal(str(round(min(0.95, max(0.40, conf)), 4))))


def estimate_market_rent(target: TargetAsset) -> RentEstimate:
    used_comps, dropped_comps = _fetch_comps()

    if not used_comps:
        raise ValueError("No usable comps in database. Run ingest first.")

    rents = [float(c.rent_psf_yr) for c in used_comps]  # type: ignore[arg-type]
    confs = [c.confidence or 0.80 for c in used_comps]

    # ── BASE: confidence-weighted average of all valid comp rents ──────────────
    base_float = _weighted_avg(rents, confs)
    base = _q(_d(base_float))

    sky_harbor_count = sum(1 for c in used_comps if c.submarket == "Sky Harbor")
    cv = statistics.stdev(rents) / base_float if len(rents) > 1 else 0.0

    waterfall: list[WaterfallStep] = []

    # ── STEP 1: TIME ───────────────────────────────────────────────────────────
    # Bring all comps to as_of date using a flat 3%/yr appreciation ramp.
    # Each comp's "lag" is (as_of - signed_date); average lag drives the adjustment.
    as_of = target.as_of
    lags_years = [
        (as_of - date.fromisoformat(c.signed_date)).days / 365.25
        for c in used_comps
    ]
    avg_lag_years = _d(sum(lags_years) / len(lags_years))
    # Compound factor: (1 + r)^t − 1
    time_factor = (1 + TIME_ANNUAL_RATE) ** avg_lag_years - 1
    after_time = _q(base * (1 + time_factor))

    waterfall.append(
        _step(
            "Time",
            base,
            after_time,
            f"Avg comp signed {float(avg_lag_years):.2f} yrs before as_of "
            f"({as_of}). Assumption: {float(TIME_ANNUAL_RATE)*100:.0f}%/yr flat "
            f"Phoenix industrial appreciation. Factor: ×{float(1+time_factor):.4f}.",
        )
    )

    # ── STEP 2: SIZE ───────────────────────────────────────────────────────────
    # Larger leases price lower per SF. If the comp pool skews larger than the target,
    # comp rents understate what the target would fetch → positive adjustment, and v.v.
    # Rate: 1.5% per 50,000 SF difference.
    sf_values = [c.lease_sf for c in used_comps if c.lease_sf]
    avg_comp_sf = sum(sf_values) / len(sf_values) if sf_values else target.total_sf
    sf_diff_units = _d(avg_comp_sf - target.total_sf) / _d(50_000)
    size_adj = sf_diff_units * SIZE_RATE_PER_50K_SF
    after_size = _q(after_time * (1 + size_adj))

    waterfall.append(
        _step(
            "Size",
            after_time,
            after_size,
            f"Avg comp: {avg_comp_sf:,.0f} SF vs target: {target.total_sf:,} SF "
            f"(diff {avg_comp_sf - target.total_sf:+,.0f} SF). "
            f"Rate: {float(SIZE_RATE_PER_50K_SF)*100:.1f}% per 50 k SF. "
            f"Larger spaces price lower per SF; positive adj when comps are bigger.",
        )
    )

    # ── STEP 3: CLEAR HEIGHT ───────────────────────────────────────────────────
    # Target is 32 ft. Lower-clearance comps trade at a discount; we add back that
    # premium. Rate: 0.6% per foot delta. A 24-ft comp is not just "different" from
    # a 32-ft target — it is functionally inferior for high-bay logistics tenants.
    ht_values = [c.clear_height_ft for c in used_comps if c.clear_height_ft]
    avg_comp_ht = sum(ht_values) / len(ht_values) if ht_values else target.clear_height_ft
    ht_diff = _d(target.clear_height_ft - avg_comp_ht)
    height_adj = ht_diff * HEIGHT_RATE_PER_FT
    after_height = _q(after_size * (1 + height_adj))

    waterfall.append(
        _step(
            "Clear Height",
            after_size,
            after_height,
            f"Target: {target.clear_height_ft} ft clear; avg comp: {avg_comp_ht:.1f} ft "
            f"(diff {float(ht_diff):+.1f} ft). Rate: {float(HEIGHT_RATE_PER_FT)*100:.1f}%/ft. "
            f"32-ft clear commands premium over 24-ft stock (high-bay logistics).",
        )
    )

    # ── STEP 4: VINTAGE ────────────────────────────────────────────────────────
    # Newer buildings command a premium (better dock ratios, LED lighting, ESFR sprinklers).
    # Rate: 0.35% per year newer than the comp pool average.
    vint_values = [c.year_built for c in used_comps if c.year_built]
    avg_comp_vint = sum(vint_values) / len(vint_values) if vint_values else target.year_built
    vint_diff = _d(target.year_built - avg_comp_vint)
    vintage_adj = vint_diff * VINTAGE_RATE_PER_YR
    after_vintage = _q(after_height * (1 + vintage_adj))

    waterfall.append(
        _step(
            "Vintage",
            after_height,
            after_vintage,
            f"Target built {target.year_built}; avg comp built {avg_comp_vint:.0f} "
            f"(diff {float(vint_diff):+.1f} yrs). Rate: {float(VINTAGE_RATE_PER_YR)*100:.2f}%/yr. "
            f"Newer buildings carry premium for modern systems.",
        )
    )

    # ── POINT ESTIMATE ─────────────────────────────────────────────────────────
    point_estimate = after_vintage  # guaranteed: waterfall[-1].after == point_estimate

    # ── BAND ───────────────────────────────────────────────────────────────────
    # Use percentile spread of individual comp rents (after time-normalizing each) as
    # the basis for low/high, then apply the same non-time adjustments to keep them
    # consistent with the waterfall.
    non_time_factor = (1 + size_adj) * (1 + height_adj) * (1 + vintage_adj)
    time_adjusted_rents = sorted(
        r * float((1 + TIME_ANNUAL_RATE) ** _d(lag))
        for r, lag in zip(rents, lags_years)
    )

    if len(time_adjusted_rents) >= 4:
        n = len(time_adjusted_rents)
        p15_idx = max(0, int(n * 0.15))
        p85_idx = min(n - 1, int(n * 0.85))
        low_raw = time_adjusted_rents[p15_idx]
        high_raw = time_adjusted_rents[p85_idx]
    else:
        std = statistics.stdev(time_adjusted_rents) if len(time_adjusted_rents) > 1 else 0.5
        low_raw = float(after_time) - std
        high_raw = float(after_time) + std

    low = _q(_d(low_raw) * non_time_factor)
    high = _q(_d(high_raw) * non_time_factor)

    avg_conf = _weighted_avg(confs, confs)
    overall_conf = _overall_confidence(used_comps, avg_conf, cv, sky_harbor_count)

    return RentEstimate(
        point_estimate_psf_yr=point_estimate,
        low=low,
        high=high,
        confidence=overall_conf,
        comp_count_used=len(used_comps),
        comp_count_dropped=len(dropped_comps),
        waterfall=waterfall,
        comps_used=used_comps,
        comps_dropped=dropped_comps,
    )
