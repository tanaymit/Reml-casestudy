# NOTES.md

## Time Spent

~3.5 hours total.

- **~30 min** reading the brief and studying the CSV very carefully before writing code.
  Found all four monthly-quoted rows, both duplicates, identified the submarket landscape.
- **~50 min** ingest layer: designed the confidence model, wrote duplicate resolution,
  unit-conversion detection, and off-submarket exclusion. Ran sanity checks against the DB.
- **~60 min** estimation engine: designed the waterfall, verified Decimal arithmetic,
  confirmed the headline number reconstructs exactly from top-to-bottom.
- **~45 min** FastAPI + Pydantic models, CORS, validation errors.
- **~35 min** Next.js UI: waterfall table, comps tabs, hero card, methodology panel.
- **~20 min** git hygiene, README, NOTES.md.

---

## Assumptions

**1. Time ramp is a flat 3%/yr.**
Phoenix industrial rents grew 5–8%/yr in 2022–23 and moderated to 2–4% in 2024–25.
I used 3% as a conservative through-cycle assumption rather than trying to fit a curve
to a dataset that has no pricing-index anchor. A domain expert could supply a better ramp
(e.g., CoStar rent index for Sky Harbor) and the waterfall would update cleanly.

**2. Deer Valley and Goodyear are "clearly outside" the target's market.**
The brief says "a few rows in a submarket clearly outside the target's market." I read
this as Deer Valley (north Scottsdale corridor, 25+ miles from Sky Harbor) and Goodyear
(far west Valley, different tenant base). Southwest Phoenix and Tolleson are adjacent to
Sky Harbor and serve the same logistics/distribution demand; I kept them with confidence
multipliers (0.90× and 0.85× respectively) rather than excluding them. If a domain expert
says Tolleson is too far, it's a one-line change.

**3. Confidence is multiplicative across source × submarket × data-completeness factors.**
I had no prior data to calibrate this — it reflects my intuition about the relative
trustworthiness of institutional broker reports vs. broker flyers vs. internal records.
The confidence score drives the weighted average but not the adjustment rationale.
A calibrated model would need a holdout set of "known" rents.

---

## What I'd Fix Next

**1. Per-comp adjustments instead of aggregate adjustments.**
The current waterfall applies adjustments to the blended average, which means a comp
that is 500,000 SF and 24 ft gets the same treatment as one that is 50,000 SF and 32 ft.
The right approach is to adjust each comp to the target's size/height/vintage/date, *then*
blend the normalized rents. The waterfall would still reconstruct, but each step's
delta_pct would reflect the actual distribution of comp characteristics rather than their
averages. I deferred this because the aggregate approach satisfies the auditability
requirement cleanly and the adjustments are small (the comp pool average is close to the
target on most dimensions).

**2. A fitted time trend rather than a flat ramp.**
With signed_date spanning 2022–2025, you can fit a simple OLS regression of rent on
date (for the Sky Harbor pool) to get a market-specific trend. This would replace the
assumed 3% with an empirical estimate and give a standard error for the time adjustment
that could widen the confidence band appropriately for old comps.

**3. Source-specific bias correction for broker_flyer comps.**
Broker flyers historically over-report asking rents (they reflect marketing, not
execution). A correction factor — estimated from cases where the same deal appears in
both a flyer and a broker report — would make the confidence model more meaningful. Right
now I apply a blanket 0.80 confidence multiplier, which is directionally correct but not
calibrated.

---

## Questions for a Domain Expert

**1. What is the standard adjustment rate for clear height in the Sky Harbor market?**
I used 0.6%/ft based on published industrial valuation guidelines. But Phoenix's extreme
heat affects tenant preferences around dock doors and building envelope in ways that may
make height premiums different here than in, say, Chicago or New Jersey. Is 0.6%/ft
reasonable for this submarket, or does it need to be split by height tier (e.g., 24→28 ft
vs. 28→32 ft vs. 32→36 ft have different elasticities)?

**2. How should Tolleson comps be weighted relative to Sky Harbor?**
I applied a 0.85× confidence multiplier for Tolleson on the assumption that it competes
for similar tenants (cross-dock logistics, e-commerce fulfillment) as Sky Harbor. But
Tolleson is west of the I-10/Loop 101 interchange and may represent a slightly different
submarket with different absorption and TI structures. Should Tolleson comps be excluded
entirely, or weighted further down?

**3. For the duplicate `83970 S 47th Ave` (JLL: $10.12 vs. broker_flyer: $10.26), which
rent is execution?**
I averaged the two figures ($10.19 blended) and applied a 0.90× confidence penalty for
the discrepancy. In practice: does the JLL figure reflect net effective rent while the
broker flyer reflects asking rent? Or could one source be reporting the wrong transaction
leg (e.g., gross vs. NNN)? Knowing the source convention would tell me whether to always
prefer the institutional broker over the flyer, or to use the lower figure as the
conservative estimate for an investment-committee memo.
