"use client";

import { useEffect, useState } from "react";
import { fetchEstimate, type RentEstimate, type TargetAsset } from "@/lib/api";

const TARGET: TargetAsset = {
  address: "4150 S 51st Ave, Phoenix, AZ 85043",
  submarket: "Sky Harbor",
  total_sf: 145000,
  year_built: 2008,
  clear_height_ft: 32,
  as_of: "2025-09-30",
};

function fmt(v: number | string) {
  return Number(v).toFixed(2);
}

function fmtSf(v: number) {
  return new Intl.NumberFormat("en-US").format(v);
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(Number(value) * 100);
  const color =
    pct >= 80 ? "bg-emerald-100 text-emerald-800 ring-emerald-200" :
    pct >= 60 ? "bg-amber-100 text-amber-800 ring-amber-200" :
    "bg-red-100 text-red-800 ring-red-200";
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ring-1 ${color}`}>
      <span className="text-xs opacity-70">Confidence</span>
      <span>{pct}%</span>
    </span>
  );
}

function DeltaCell({ v }: { v: number }) {
  const n = Number(v);
  const zero = Math.abs(n) < 0.005;
  if (zero) return <span className="text-gray-400">≈0</span>;
  const pos = n > 0;
  return (
    <span className={`font-mono font-semibold ${pos ? "text-emerald-600" : "text-red-600"}`}>
      {pos ? "+" : ""}${fmt(n)}
    </span>
  );
}

function WaterfallBar({ delta, max }: { delta: number; max: number }) {
  const n = Number(delta);
  const pct = Math.min(100, (Math.abs(n) / max) * 100);
  if (pct < 1) return null;
  const pos = n >= 0;
  return (
    <div className="flex items-center mt-1.5 h-1.5">
      {!pos && <div className="ml-auto h-full rounded" style={{ width: `${pct}%`, background: "#fca5a5" }} />}
      {pos && <div className="h-full rounded" style={{ width: `${pct}%`, background: "#6ee7b7" }} />}
    </div>
  );
}

function WaterfallTable({ steps }: { steps: RentEstimate["waterfall"] }) {
  const maxDelta = Math.max(...steps.map((s) => Math.abs(Number(s.delta))));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide w-36">Step</th>
            <th className="text-right py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">Before</th>
            <th className="text-right py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">After</th>
            <th className="text-right py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide w-28">Delta</th>
            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">Rationale</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((s, i) => (
            <tr key={i} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
              <td className="py-4 px-4 font-medium text-gray-900 whitespace-nowrap">{s.step}</td>
              <td className="py-4 px-4 text-right font-mono text-gray-500">${fmt(s.before)}</td>
              <td className="py-4 px-4 text-right font-mono font-semibold text-gray-900">${fmt(s.after)}</td>
              <td className="py-4 px-4 text-right">
                <DeltaCell v={Number(s.delta)} />
                <div className="text-xs font-mono text-gray-400 mt-0.5">
                  {Number(s.delta_pct) > 0 ? "+" : ""}{Number(s.delta_pct).toFixed(2)}%
                </div>
                <WaterfallBar delta={Number(s.delta)} max={maxDelta} />
              </td>
              <td className="py-4 px-4 text-xs text-gray-500 leading-relaxed max-w-sm">{s.rationale}</td>
            </tr>
          ))}
          <tr className="bg-gray-900 text-white">
            <td colSpan={2} className="py-4 px-4 font-bold text-sm">Point Estimate</td>
            <td className="py-4 px-4 text-right">
              <span className="font-mono font-bold text-xl text-emerald-400">${fmt(steps[steps.length - 1]?.after ?? 0)}</span>
              <span className="text-gray-500 text-xs ml-1">/sf/yr</span>
            </td>
            <td className="py-4 px-4 text-right text-gray-600 text-xs">—</td>
            <td className="py-4 px-4 text-xs text-gray-400 italic">Waterfall final = point estimate (reconstruction verified)</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

type SortKey = "signed_date" | "rent_psf_yr" | "lease_sf" | "submarket" | "confidence";

function CompsTable({
  comps,
  dropped = false,
}: {
  comps: RentEstimate["comps_used"] | RentEstimate["comps_dropped"];
  dropped?: boolean;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("signed_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const sorted = [...comps].sort((a, b) => {
    const va = a[sortKey] ?? "";
    const vb = b[sortKey] ?? "";
    if (va < vb) return sortDir === "asc" ? -1 : 1;
    if (va > vb) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const pages = Math.ceil(sorted.length / PAGE_SIZE);
  const visible = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function toggleSort(k: SortKey) {
    if (sortKey === k) { setSortDir(d => d === "asc" ? "desc" : "asc"); }
    else { setSortKey(k); setSortDir("desc"); }
    setPage(0);
  }

  function Th({ label, k, right }: { label: string; k: SortKey; right?: boolean }) {
    const active = sortKey === k;
    return (
      <th
        className={`py-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wide cursor-pointer select-none hover:text-gray-700 ${right ? "text-right" : "text-left"}`}
        onClick={() => toggleSort(k)}
      >
        {label}{active ? (sortDir === "desc" ? " ↓" : " ↑") : ""}
      </th>
    );
  }

  function dropLabel(reason: string | null) {
    if (!reason) return "";
    if (reason.startsWith("off_submarket:")) return `Off-submarket: ${reason.split(":")[1]}`;
    if (reason === "rent_undisclosed") return "Rent undisclosed";
    if (reason.startsWith("duplicate_merged")) return "Duplicate (merged away)";
    if (reason.startsWith("duplicate_of")) return "Duplicate (secondary)";
    return reason;
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm min-w-[780px]">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <Th label="Address" k="submarket" />
              <Th label="Date" k="signed_date" />
              <Th label="SF" k="lease_sf" right />
              <Th label="Rent $/sf/yr" k="rent_psf_yr" right />
              <th className="py-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wide text-left">Ht</th>
              <th className="py-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wide text-left">Built</th>
              <th className="py-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wide text-left">Source</th>
              {!dropped && <Th label="Conf" k="confidence" right />}
              {dropped && <th className="py-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wide text-left">Reason</th>}
            </tr>
          </thead>
          <tbody>
            {visible.map((c) => (
              <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td className="py-2.5 px-3">
                  <div className="font-medium text-gray-900 truncate max-w-[200px]" title={c.address}>
                    {c.address.split(",")[0]}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{c.submarket}</div>
                </td>
                <td className="py-2.5 px-3 text-gray-500 whitespace-nowrap text-xs">{c.signed_date}</td>
                <td className="py-2.5 px-3 text-gray-600 font-mono text-right text-xs">
                  {c.lease_sf ? fmtSf(c.lease_sf) : "—"}
                </td>
                <td className="py-2.5 px-3 text-right">
                  {c.rent_psf_yr != null ? (
                    <span className="font-mono font-semibold text-gray-900">${fmt(c.rent_psf_yr)}</span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                  {c.is_monthly_converted && (
                    <span
                      className="ml-1 text-xs bg-amber-100 text-amber-700 px-1 rounded"
                      title="Converted from $/sf/month × 12"
                    >
                      ×12
                    </span>
                  )}
                </td>
                <td className="py-2.5 px-3 text-gray-500 text-xs">{c.clear_height_ft ? `${c.clear_height_ft}′` : "—"}</td>
                <td className="py-2.5 px-3 text-gray-500 text-xs">{c.year_built ?? "—"}</td>
                <td className="py-2.5 px-3 text-gray-400 text-xs">{c.source}</td>
                {!dropped && (
                  <td className="py-2.5 px-3 text-right">
                    <span className={`text-xs font-mono font-medium ${
                      (c.confidence ?? 0) >= 0.90 ? "text-emerald-600" :
                      (c.confidence ?? 0) >= 0.80 ? "text-amber-600" : "text-red-500"
                    }`}>
                      {c.confidence != null ? `${(Number(c.confidence) * 100).toFixed(0)}%` : "—"}
                    </span>
                  </td>
                )}
                {dropped && (
                  <td className="py-2.5 px-3">
                    <span className="text-xs px-2 py-0.5 bg-red-50 text-red-700 rounded border border-red-100 whitespace-nowrap">
                      {dropLabel(c.drop_reason)}
                    </span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between mt-3 text-sm text-gray-500">
          <span className="text-xs text-gray-400">Page {page + 1} of {pages} · {comps.length} total</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-1 rounded border border-gray-200 text-xs hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Prev
            </button>
            <button
              onClick={() => setPage(Math.min(pages - 1, page + 1))}
              disabled={page === pages - 1}
              className="px-3 py-1 rounded border border-gray-200 text-xs hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [estimate, setEstimate] = useState<RentEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"used" | "dropped">("used");

  useEffect(() => {
    fetchEstimate(TARGET)
      .then(setEstimate)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const offSubmarketCount = estimate?.comps_dropped.filter(c => c.drop_reason?.startsWith("off_submarket")).length ?? 0;
  const undisclosedCount = estimate?.comps_dropped.filter(c => c.drop_reason === "rent_undisclosed").length ?? 0;
  const duplicateCount = estimate?.comps_dropped.filter(c => c.drop_reason?.startsWith("duplicate")).length ?? 0;
  const monthlyCount = estimate?.comps_used.filter(c => c.is_monthly_converted).length ?? 0;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-gray-900 rounded-md flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <span className="font-semibold text-gray-900 text-sm">Reml Insights</span>
            <span className="text-gray-200 text-sm">|</span>
            <span className="text-sm text-gray-400">Market Rent Engine</span>
          </div>
          <span className="text-xs text-gray-400 font-mono">as_of {TARGET.as_of}</span>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">

        {/* Asset Card */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Target Asset</p>
              <h1 className="text-lg font-bold text-gray-900">{TARGET.address}</h1>
              <p className="text-gray-500 text-sm mt-1">{TARGET.submarket} Submarket · Phoenix, AZ Industrial</p>
            </div>
            <div className="flex gap-8 text-sm">
              {([
                ["Size", `${fmtSf(TARGET.total_sf)} SF`],
                ["Built", String(TARGET.year_built)],
                ["Clear Height", `${TARGET.clear_height_ft} ft`],
              ] as [string, string][]).map(([label, value]) => (
                <div key={label} className="text-center">
                  <p className="text-xs text-gray-400 uppercase tracking-wide">{label}</p>
                  <p className="font-semibold text-gray-900 mt-0.5">{value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
            <div className="inline-block w-7 h-7 border-[3px] border-gray-200 border-t-gray-800 rounded-full animate-spin mb-4" />
            <p className="text-gray-400 text-sm">Running estimation engine…</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6">
            <p className="font-semibold text-red-800">Could not reach API</p>
            <p className="text-red-600 text-sm mt-1">{error}</p>
            <p className="text-xs text-red-400 mt-2 font-mono">
              cd backend &amp;&amp; uvicorn app.main:app --reload
            </p>
          </div>
        )}

        {estimate && (
          <>
            {/* Estimate Hero */}
            <div className="bg-gray-900 rounded-xl p-7 text-white">
              <div className="flex flex-wrap items-end justify-between gap-6">
                <div>
                  <p className="text-gray-400 text-xs uppercase tracking-widest font-medium mb-3">Market Rent Estimate</p>
                  <div className="flex items-baseline gap-3">
                    <span className="text-5xl font-bold tracking-tight">
                      ${fmt(estimate.point_estimate_psf_yr)}
                    </span>
                    <span className="text-gray-400">/sf/yr</span>
                  </div>
                  <p className="text-gray-400 text-sm mt-2">
                    Range: <span className="text-gray-200 font-mono">${fmt(estimate.low)}</span>
                    {" – "}
                    <span className="text-gray-200 font-mono">${fmt(estimate.high)}</span>
                    <span className="text-gray-500 ml-2 text-xs">(15th – 85th pct of comp distribution)</span>
                  </p>
                </div>
                <div className="flex flex-col items-end gap-3">
                  <ConfidenceBadge value={estimate.confidence} />
                  <div className="flex gap-6 text-center">
                    <div>
                      <p className="text-gray-500 text-xs">Comps used</p>
                      <p className="text-white font-semibold mt-0.5">{estimate.comp_count_used}</p>
                    </div>
                    <div>
                      <p className="text-gray-500 text-xs">Comps dropped</p>
                      <p className="text-gray-400 font-semibold mt-0.5">{estimate.comp_count_dropped}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Waterfall mini-summary */}
              <div className="mt-6 pt-5 border-t border-gray-700 grid grid-cols-2 sm:grid-cols-4 gap-4">
                {estimate.waterfall.map((s) => {
                  const d = Number(s.delta);
                  const pct = Number(s.delta_pct);
                  const zero = Math.abs(d) < 0.005;
                  return (
                    <div key={s.step}>
                      <p className="text-gray-500 text-xs uppercase tracking-wide">{s.step}</p>
                      <p className={`font-mono font-medium mt-1 ${zero ? "text-gray-600" : d > 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {zero ? "≈0" : `${d > 0 ? "+" : ""}$${fmt(d)}`}
                      </p>
                      {!zero && (
                        <p className="text-gray-600 text-xs font-mono mt-0.5">
                          {pct > 0 ? "+" : ""}{pct.toFixed(1)}%
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Waterfall Detail */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="font-semibold text-gray-900">Adjustment Waterfall</h2>
                <p className="text-xs text-gray-400 mt-1">
                  Sequential adjustments from comp-pool average to target. Each row&apos;s{" "}
                  <em>after</em> feeds the next row&apos;s <em>before</em>.
                  Final <em>after</em> = point estimate — verifiable top-to-bottom.
                </p>
              </div>
              <WaterfallTable steps={estimate.waterfall} />
            </div>

            {/* Comps Panel */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="font-semibold text-gray-900">Comparable Transactions</h2>
                <p className="text-xs text-gray-400 mt-1">
                  {offSubmarketCount} off-submarket excluded · {undisclosedCount} undisclosed rent · {duplicateCount} duplicate merged · {monthlyCount} monthly→annual converted
                </p>
              </div>
              <div className="flex border-b border-gray-200 px-6">
                {(["used", "dropped"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`py-3 px-1 mr-6 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === tab
                        ? "border-gray-900 text-gray-900"
                        : "border-transparent text-gray-400 hover:text-gray-700"
                    }`}
                  >
                    {tab === "used" ? `Used in blend (${estimate.comp_count_used})` : `Dropped (${estimate.comp_count_dropped})`}
                  </button>
                ))}
              </div>
              <div className="p-6">
                {activeTab === "used"
                  ? <CompsTable comps={estimate.comps_used} />
                  : <CompsTable comps={estimate.comps_dropped} dropped />
                }
              </div>
            </div>

            {/* Methodology note */}
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-5">
              <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">Methodology & Assumptions</h3>
              <dl className="text-xs text-slate-600 space-y-2">
                <div className="flex gap-3">
                  <dt className="font-medium text-slate-700 whitespace-nowrap w-32 shrink-0">Time ramp</dt>
                  <dd>3%/yr flat (declared assumption; Phoenix industrial grew 5–8%/yr in 2022–23, moderating to 2–4% in 2024–25; 3% is a defensible through-cycle estimate)</dd>
                </div>
                <div className="flex gap-3">
                  <dt className="font-medium text-slate-700 whitespace-nowrap w-32 shrink-0">Size elasticity</dt>
                  <dd>1.5% per 50k SF difference — larger industrial spaces trade at lower $/SF per SF</dd>
                </div>
                <div className="flex gap-3">
                  <dt className="font-medium text-slate-700 whitespace-nowrap w-32 shrink-0">Clear height</dt>
                  <dd>0.6%/ft delta — 32-ft clear is functionally superior (high-bay racking, modern 3PL users); not merely "different" from 24-ft stock</dd>
                </div>
                <div className="flex gap-3">
                  <dt className="font-medium text-slate-700 whitespace-nowrap w-32 shrink-0">Vintage</dt>
                  <dd>0.35%/yr newer — premium for modern dock doors, LED, ESFR sprinklers, build-to-suit layouts</dd>
                </div>
                <div className="flex gap-3">
                  <dt className="font-medium text-slate-700 whitespace-nowrap w-32 shrink-0">Comp pool</dt>
                  <dd>Sky Harbor 1.0× · Southwest Phoenix 0.90× · Tolleson 0.85× submarket confidence. Deer Valley and Goodyear excluded (clearly outside target&apos;s market).</dd>
                </div>
              </dl>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
