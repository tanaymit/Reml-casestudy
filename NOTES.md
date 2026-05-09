# NOTES.md

## Time Spent

About 3.5 hours total.

**30 min** reading the brief and studying the CSV before touching the editor. Genuinely the most valuable half hour. Found all four monthly-quoted rows, both duplicate pairs, and mapped out the submarket landscape. The temptation to just start coding is real, but the data quality issues here are the whole problem.

**50 min** ingest layer: confidence model, duplicate resolution, unit-conversion detection, off-submarket exclusion. Ran sanity checks against the DB to confirm counts matched expectations.

**60 min** estimation engine: designed the waterfall, verified Decimal arithmetic throughout (no floats near money), confirmed the headline number reconstructs exactly top to bottom.

**45 min** FastAPI and Pydantic models, CORS, validation error handling.

**35 min** Next.js UI: waterfall table, comps tabs, hero card, methodology panel.

**20 min** git cleanup, README, NOTES.


## Assumptions

**1. Time ramp is a flat 3%/yr.**

Phoenix industrial rents grew 5 to 8%/yr in 2022-23 and moderated to 2 to 4% in 2024-25. I picked 3% as a conservative through-cycle number rather than fitting a curve to a dataset with no pricing-index anchor. A domain expert could plug in a CoStar Sky Harbor rent index and the waterfall would update cleanly without touching any other logic.

**2. Deer Valley and Goodyear are out. Tolleson and Southwest Phoenix stay, with a haircut.**

Deer Valley is north Scottsdale, 25+ miles from Sky Harbor with a completely different tenant profile. Goodyear is far west Valley. Both dropped.

Tolleson and Southwest Phoenix are adjacent to Sky Harbor and serve the same logistics and distribution demand, so I kept them with confidence multipliers (0.90x and 0.85x respectively) instead of throwing them away. If a domain expert says Tolleson is too far, it is literally a one-line change.

**3. Confidence is multiplicative: source x submarket x data completeness.**

I had no calibration data, so the weights reflect my best intuition about how much to trust institutional broker reports versus broker flyers versus internal records. The score drives the weighted average blend but does not affect the adjustment rationale. To make it rigorous you would need a holdout set of known executed rents to fit against.


## What I Would Fix Next

**1. Per-comp adjustments instead of adjusting the blended average.**

Right now the waterfall adjusts the pool average, which means a 500,000 SF 24-ft comp and a 50,000 SF 32-ft comp get the same treatment. The correct approach is to normalize each comp individually to the target's size, height, vintage, and date, then blend the normalized rents. The waterfall would still reconstruct; each step's delta would just reflect the actual distribution of comp characteristics rather than their averages. I deferred this because the pool average is close enough to the target on most dimensions that the error is small, and the aggregate approach satisfies the auditability requirement cleanly.

**2. A fitted time trend instead of a declared flat ramp.**

With signed_date spanning 2022 to 2025 there is enough history to run a simple OLS regression of rent on date for the Sky Harbor pool. That replaces the assumed 3% with an empirical estimate and produces a standard error, which could widen the confidence band for older comps in a principled way.

**3. Source-specific bias correction for broker flyer comps.**

Broker flyers report asking rents, not executed rents. The gap is real and consistent. A proper correction factor would be estimated from cases where the same deal appears in both a flyer and a broker report, then applied as a multiplier. Right now I use a blanket 0.80 confidence weight, which is directionally correct but not calibrated to any actual data.


## Questions for a Domain Expert

**1. Is 0.6%/ft the right clear height premium for Sky Harbor?**

I used 0.6%/ft from published industrial valuation guidelines. Phoenix heat may affect tenant preferences around dock doors and building envelope in ways that make height premiums behave differently here than in, say, Chicago or New Jersey. Does 0.6%/ft hold for this submarket, or should it be tiered by height bracket (24 to 28 ft vs. 28 to 32 ft vs. 32 to 36 ft might each have different elasticities)?

**2. How much should Tolleson comps be discounted relative to Sky Harbor?**

I used 0.85x on the assumption that Tolleson competes for similar cross-dock logistics and e-commerce tenants. But it sits west of the I-10/Loop 101 interchange and may have different absorption dynamics and TI structures. Should Tolleson comps be excluded entirely, or just discounted further?

**3. For the duplicate at 83970 S 47th Ave (JLL: $10.12 vs. broker flyer: $10.26), which number reflects execution?**

I averaged to $10.19 and applied a 0.90x confidence penalty for the discrepancy. The real question is whether the JLL figure is net effective rent while the flyer is asking rent, or whether one source reported a different transaction leg entirely (gross vs. NNN). Knowing the source convention would clarify whether to always prefer the institutional broker figure, or to use the lower number as the conservative estimate for an investment-committee memo.
