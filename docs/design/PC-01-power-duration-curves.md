# PC-01 — Power-Duration Curves (Performance and Activity Review)

**Status:** Owner-directed design baseline, 2026-10-11. **Implementation not started.**
**Scope:** A new bounded Performance follow-up, independent of deferred Phase 6 adaptive planning.
**Source:** Owner-provided Strava Best Efforts Power Curve screenshot and explicit selection of **previous six weeks** as the default Activity Review comparison.
**References:** [Product requirements](../PRODUCT_REQUIREMENTS.md) (`REV-003`, `REV-004`, `PERF-001`–`005`), accepted [Phase 2 Performance](../PHASE_2_ACCEPTANCE.md), accepted [Activity Review mockup](../mockups/README.md). The Strava screenshot is *visual/interaction inspiration*, **not** the calculation/eligibility specification.

## 1. Product question and owner-confirmed behavior

Power-duration curves should answer:
- **Performance:** "What is the strongest power I've sustained for different durations, and how does a chosen period compare with another?"
- **Activity Review:** "How does this ride's best-effort profile compare with the **six weeks preceding it**?"

**Default in Activity Review:** The selected activity versus the prior **rolling 42 × 24 hours before its own start instant**: `[selected_start - 42 days, selected_start)`. **Exclude the selected ride** even if data association/date processing changes, and exclude all activities occurring at/after the selected ride start, i.e., **no future leakage** on historical rides. If an activity's absolute start is unknown, do not invent a prior 42-day window; show a clear unavailable/default comparison explanation. Timezone is relevant to display/labels, not to the absolute past interval.

**Placement:** Preserve established navigation and charts. On the existing **Performance** page add a **Power Curve** view alongside its accepted **20-Minute History**; don't remove or recalculate the accepted history. In **Activity Review**, add a distinct **Power Curve** section/tab within its accepted analysis hierarchy; preserve power/HR time-series, source details, current 20-minute summary and planner context. Power Curve compares the selected ride with prior-history overlays (default previous six weeks).

**Comparison controls:** Performance has two independently selectable, distinctly colored/labelled periods, e.g. **Last 6 weeks**, **Previous 6 weeks**, **Year to date**, **Previous calendar year**, **All time**. Initial comparison default may be Last 6 weeks vs All time (working UI default; not Owner-set), and avoid suggesting one is guaranteed better or independent if they overlap. Activity Review defaults to **This ride versus its previous six weeks**; allow **Prior 12 months** and **All history before this ride** as alternatives, with optional overlay hiding. Period semantics, inclusive/exclusive ends and current/historic date anchors must be explicitly labeled. Custom period pickers and third/fourth simultaneous datasets are future candidates, not v1 obligations.

## 2. What is being calculated

For every **eligible contiguous duration window** with real supported observed power, calculate its **arithmetic average watts**, and take the **maximum** among qualifying windows of the same duration. For any cohort/period curve, take the **maximum eligible duration-specific result across all rides within that period**. This is a **maximal mean power (MMP) / power-duration** curve, **not fitted critical power**. Peak recorded instantaneous power is not a substitute for the shortest averaging duration.

- Use native FIT-supported or accepted Strava API time/watts evidence under the current **trusted Virtual Ride performance-source policy** as the default eligible cohort; source selection must be unambiguous and reproducible. A file-backed candidate takes precedence over an API source per existing policy. **CSV/summary power, training stress, dated FTP, HR-based estimated power or P4-02 estimated session PSS do not create new sampled watts.** Do not silently expand Outdoor Ride eligibility from the existing Performance v2 policy. A ride outside the cohort gets an honest unavailable reason, not a fabricated zero curve.
- Watts of **zero** are real observations. Missing watts, invalid/duplicate/backwards timestamps, unreconciled sample gaps and unsupported source/timer evidence cannot be silently turned into real observations. Calculate only fully supported continuous windows, with no gaps bridged, no unverified pause splicing, and no filling unknown samples with zero. Distinguish *available at short durations* from *unavailable at long durations* for interrupted rides. The existing 20-minute current method uses **complete consecutive 1 Hz sample windows**; preserve parity for exactly 1,200 s on the same eligible source.
- Display at useful short and long durations on a **logarithmic duration axis** (e.g. 1 s, 5 s, 15 s, 30 s, 1 m, 3 m, 5 m, 10 m, 20 m, 30 m, 1 h, with longer durations when truly supported), adjusting end time to real data. Duration labels are durations, not calendar dates. No claim of a computed exact result at interpolated uncalculated durations: if rendering only a set of evaluated durations, distinguish connected visual lines from measured/computed anchor results in hover/readout. Avoid overly sparse duration sampling that produces a misleading curve, but also avoid brute-force all-second × all-ride computation that may block normal page use. Dex should propose a practical accuracy/performance balance and document exact queryable durations for v1.
- Historical period MMP is the **envelope** of best eligible mean-power efforts *from different rides*. It is not one continuous ride, and each inspected duration should identify its **contributing Activity/date/source** and precise duration, watts and confidence/eligibility label. When curves intersect, the contributing ride may change. Ties have a deterministic policy.
- **Period bests are not a performance test of the rider:** Sprint near-maximums, VO2 repeats, threshold work and long endurance may originate from different workouts. Display comparisons neutrally. No automatic FTP estimate, CP/W′ fitting, progression prescriptions or readiness inference in v1.

## 3. Chart and interactions

### Performance
- An in-page **20-Minute History | Power Curve** mode control (current 20-minute graph remains default initially as a working assumption to avoid regressions).
- Primary large graph with logarithmic duration X, watts Y, two contrasting line/point series selected by independent period controls; clear legend showing period bounds and counts of eligible rides contributing.
- Hover/focus tooltip: **duration, exact computed watts for both series when supported, contributing ride title/date, click/open Activity**. A side or below-plot selected-effort readout works on touch/mobile and with keyboard. Use explicit "Unavailable at this duration" where needed, not zero or extrapolated ends.
- Optional individual series toggles, neutral difference readout at inspection and reasonable y-scale. Prefer the existing RideWorks SVG/color/type hierarchy over copying Strava branding.

### Activity Review
- Existing activity chart/metrics retained; separate **Power Curve** section/tab, default **This ride + Previous six weeks**, with a period selector for other *historically prior* comparison ranges and a legend.
- Reuse same math, source policy, duration positions and inspected-effort readout. A ride's curve cannot extend beyond its longest qualifying window; the historical baseline may extend longer. Historical curve is anchored before the reviewed ride, not after it.
- Tooltip/readout includes both curves and source ride link. Click from historical line to contributing activity; current ride link remains itself.
- Show honest "No qualifying power data" for missing or ineligible current activity (including outdoor when not trusted), and "No qualifying rides in previous six weeks" where the selected ride qualifies but has no baseline.

**Editable UI reference:** [PC-01 power-curve HTML design](../mockups/power-curve-v1.html) illustrates the hierarchy on both screens. It uses **synthetic** curves, labels and rides; don't use its numbers as verification or claim it's a pre-approved final screenshot. Owner visual acceptance follows implementation.

## 4. Computation/reuse/performance boundary

- Existing `rideworks/analysis.py` implements `best_20_minute_power()` as a complete one-second 1,200-s window. `rideworks/performance.py` maintains the trusted Virtual Ride evidence cohort and date/timing policy. **Reuse those policies and test exact 20-minute parity** rather than inventing a conflicting best-effort definition.
- A multi-duration power profile over ~1,000 source-backed rides is more expensive than a single 20-minute best. **On-demand whole-archive rescans whenever hovering, visiting Performance or Activity Review, or switching periods are unacceptable.** Evaluate a limited, reproducible per-ride derived profile/cache using existing storage conventions and invalidation by source/extraction/policy/duration method, with a safe incremental or explicit build path appropriate for a local single-rider app. Do not assume a universal index or complex distributed processing.
- Cache computed results, **not a second copy of raw streams**. Historical ranges can take maxima across cached per-ride profiles, with source/date constraints and inspectable contributing identity. Newly synced rides and updated sources should be eligible after the required computation/rebuild, without corrupting the old 20-minute Performance table.
- Compare expected input sizes, number of durations and elapsed runtime in a real representative dataset. Make an evidence-based duration/performance choice rather than silently truncating to 20 minutes or 60 minutes because computing further is inconvenient.
- No addition or modification to Strava API fetching behavior for this feature; use currently retained sources only. Preserve source files and performance/training-state methods. All new results must be versioned and recalculable.

## 5. Outstanding working assumptions (not accepted irreversible rules)

- Watts-only in v1. **Watts/kg requires historical weight** that is reliable at the contributing activity date; do not divide all historical powers by today's ~77 kg and call it accurate.
- The first trusted cohort is Virtual Ride power evidence identical to existing Performance v2; outdoor measured/estimated source eligibility warrants separate evidence/Owner approval, and need not delay delivering useful indoor curves.
- Exact plotted duration resolution, precompute/cache shape, date-range control implementation and comparison defaults on the **Performance** page are engineering/design options Dex should validate. They are **not** permission to alter the Owner-confirmed Activity Review six-week default.
- UI differences from the Strava screenshot are acceptable where they improve readability, provenance, activity linkage or accessibility.

## 6. Owner acceptance examples

1. Current qualifying indoor ride with several all-out 30/15 intervals: show truthful short duration efforts and 20-minute value; historical prior six weeks excludes current ride and *later* activity.
2. Older selected ride: baseline is anchored to that ride's own start, not today; an activity after it with stronger power must **not** change its historical comparison.
3. Two different period curves intersect; each hover duration reports the correct actual contributing ride and date from its selected period.
4. Incomplete power stream: 15 s may qualify but a 20-minute duration with gaps may be unavailable. Source explanation not made-up power.
5. Current accepted 20-minute history remains exactly consistent with v1 1,200-s result for every newly eligible shared source case; nonqualified rides remain excluded.
6. Empty baseline, missing date, CSV-only, ambiguous source and untrusted outdoor activity render honest states.
7. New sync/rebuild makes new source-backed best efforts appear without unnecessary full recomputation on every page load. Normal History/Plan/Training State and Activity Review regression passes; original artifacts are intact.

**Gate boundary:** This is an Owner-directed new Performance follow-up, **not** Phase 6. Product default is confirmed; implementer returns at HARD — Analyst then HARD — Owner visual acceptance. No completion/merge before gates.

## 7. Controlling observed-sample/timer clarification — 2026-10-11

The read-only FIT preflight in PR #28 identified conflicting paired timers and an exact terminal-stop observation. **[JIT §13](../tasks/PC-01.md) is the current controlling resolution**, superseding any broader suggestion above that all paired timer bounds must mask observed MMP samples.

**PC-01 uses Performance-style contiguous recorded 1 Hz observations as primary MMP evidence.** A source watt sample timestamp exactly coincident with a verified stop event is eligible as an *observed endpoint*, while distinct **session-verified active intervals cannot be stitched**. Mere paired timer events that conflict with session duration or later observed power are not independently verified active boundaries and **must not clip source-observed best windows**. For these cases, calculate from valid consecutive samples and retain an inspectable timer-quality caveat; don't claim timer-verified active duration. This does not change the approved Performance 20-minute chart or Training State's half-open active-time/power-stress integration. Cross-check all previously eligible shared 20-minute results; a genuinely corroborated pause causing a new parity conflict is a *narrow stop/report*, not permission to silently change Phase 2 history. No blanket exclusion of paired-but-unverified FIT sources.
