export const API_BASE = "http://localhost:8001";

export interface WaterfallStep {
  step: string;
  before: number;
  after: number;
  delta: number;
  delta_pct: number;
  rationale: string;
}

export interface CompRecord {
  id: string;
  address: string;
  submarket: string;
  signed_date: string;
  lease_sf: number | null;
  rent_psf_yr: number | null;
  year_built: number | null;
  clear_height_ft: number | null;
  source: string;
  confidence: number | null;
  status: string;
  drop_reason: string | null;
  is_monthly_converted: boolean;
}

export interface RentEstimate {
  point_estimate_psf_yr: number;
  low: number;
  high: number;
  confidence: number;
  comp_count_used: number;
  comp_count_dropped: number;
  waterfall: WaterfallStep[];
  comps_used: CompRecord[];
  comps_dropped: CompRecord[];
}

export interface TargetAsset {
  address: string;
  submarket: string;
  total_sf: number;
  year_built: number;
  clear_height_ft: number;
  as_of: string;
}

export async function fetchEstimate(target: TargetAsset): Promise<RentEstimate> {
  const res = await fetch(`${API_BASE}/api/v1/market-rent/estimate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(target),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }

  return res.json();
}

export function fmt(v: number, decimals = 2): string {
  return v.toFixed(decimals);
}

export function fmtSf(v: number): string {
  return new Intl.NumberFormat("en-US").format(v);
}
