# PC-01 Acceptance — Power-Duration Curves

**Status:** **accepted/complete 2026-10-11** after HARD — Analyst Gate 1 verification and the Owner's positive review of the implemented feature. [PR #28](https://github.com/k14krug/rideworks/pull/28).
**Scope:** New Performance/Activity Review follow-up. **Phase 6 adaptive planning remains deferred.**
**Controlling context:** [PC-01 design](design/PC-01-power-duration-curves.md), [product requirements](PRODUCT_REQUIREMENTS.md) (`REV-003`, `REV-004`, `PERF-001`–`PERF-005`), accepted [Phase 2 Performance](PHASE_2_ACCEPTANCE.md), and [editable Power Curve UI reference](mockups/power-curve-v1.html).

## Rider-visible acceptance

1. The existing Performance page offers **20-Minute History** (unchanged default and historical values) and **Power Curve**. Power Curve has an interactive log-duration horizontal axis, watts vertical axis and two **independently selectable comparison periods** (e.g. Last 6 Weeks vs All Time) with clear boundaries/legends.
2. **Activity Review** provides the selected ride's own power curve compared **by default to the previous six weeks before that activity**, not the six weeks before the user views it. Exclude the selected activity and all later rides from that baseline. The exact 42-day comparison window is anchored to the selected activity's supported absolute start.
3. Period overlays show the strongest **calculated average observed watts over continuous eligible windows** for each duration, not instantaneous watts, modeled FTP, training-load scores or pooled average data. The period curve is a maximum envelope assembled from potentially different rides. All plotted supporting durations have a real computed result. Missing/ineligible power is not plotted as 0 or bridged with invented samples.
4. Hover, touch selection and keyboard focus provide duration, watts, **contributing ride and date** and an Activity link; each curve can be inspected when another is unavailable. Results distinguish calculated from estimated/unavailable evidence. Show explicit unavailable/empty-period messages. Short and long duration signals are visually useful, not only a handful of isolated 20-minute numbers.
5. Both views follow the editable [PC-01 mockup](mockups/power-curve-v1.html), consistent with accepted RideWorks colors, density, sidebar and Activity Review hierarchy. The mockup's invented numbers and curve shapes are illustration only, not test or source data.
6. V1 defaults to **watts**; historical W/kg is not shown as trustworthy without date-appropriate weight. Outdoor power eligibility remains outside trusted Performance v2 until a separate review, and those activities do not produce an invented trusted curve.
7. The 20-minute point for any ride eligible in the existing trusted Performance cohort agrees **exactly** with the accepted `best-average-power-v1` 1,200-second window result, given the same source and identical window policy. Original existing 20-minute outputs and related charts remain unchanged.

## Required technical acceptance

- Determine and document a practical duration grid/calculation strategy with exact computed anchor durations, without pretending every visually interpolated X-value was independently evaluated; preserve log axis readability and adequate duration coverage.
- Per-ride curve derivations must be **reproducible, versioned, source-identifiable, source-aware and incremental/rebuildable** for newly synced/updated activities. No expensive rescanning of ~1,000+ full recorded ride streams on every page load or chart hover.
- Source precedence/eligibility is consistent with accepted Phase 2 principles. **Duration-specific qualification matters**: a supported 30-second window may qualify on a source that lacks any qualifying 20-minute window; do not require the 20-minute metric to be present simply to calculate short-duration power. Do not admit a competing API source solely because an existing native 20-minute window is absent when current file-backed watt evidence prohibits fallback.
- Check recording gaps, nulls, valid zero, source pauses, incomplete/stale/current streams, multiple file candidate ambiguity, trusted API high-resolution full-length conditions, unsupported Outdoor Ride, and missing/undated activity start.
- Synthetic and representative private source cases verify data provenance, period maxima by independently derived duration/window oracle, ties, crosses, historical prior-six-week exclusion of later rides, and explicit missing evidence rather than false zero. Compare **all overlapping durations** against the existing 20-minute benchmark for eligible native/API cases.
- Demonstrate local whole-archive computation/incremental update/runtime practicality (time/memory), rebuild repeatability, and normal post-sync freshness; avoid an opaque new source scoring scheme.
- Full Python tests + real Chromium desktop/mobile/keyboard controls, tooltip/readout, link targets, period changes, Home/Plan/Training State/Performance/Activities/Activity Review regression. Preserve original files, dated FTP and existing performance/stress/plan outputs and sync contract.

## Review gates and deferred scope

**HARD — Analyst Gate 1:** actual code and numerical/source/preservation/browser evidence, with visual screenshot inspection against mockup and sample anchored historic ride.
**HARD — Owner Gate 2:** running Performance Power Curve plus Activity Review comparison assessed for usefulness and clarity. No merge or done status before both gates.

**Deferred:** fitted Critical Power/W′, estimated FTP, outdoor reconstructed power, automatic workout changes, Phase 6, historical weight interpolation/W/kg, custom arbitrary period editor, and a generic ride-vs-ride comparison editor.

## Accepted Analyst timer/source contract clarification — 2026-10-11

This clarification resolves a pre-implementation numerical ambiguity; it is **not PC-01 feature acceptance or Owner Gate 2 clearance**. See [JIT §13](tasks/PC-01.md) and the [read-only diagnostic](../reports/PC-01/timer-contract-preflight.md).

- Treat FIT sample timestamps as observed records; a valid watt observation **at a verified stop timestamp may qualify as an endpoint**, while confirmed distinct active intervals never become one duration window.
- **Only independently corroborated/session-verified timer intervals are masking/splitting evidence.** Paired but contradictory/unverified timer reports do not invalidate a valid contiguous watts/timestamps sequence or clip 127 observed post-stop samples; retain source-timer quality details and do not call these timer-verified active efforts.
- Require exact best-20 value, rounded display and earliest-window parity across current 1,022 native accepted cases and supported API results. Segment verified pauses; if a concrete verified pause conflicts with existing accepted best-20 *maximum* or earliest qualifying maximum, **stop and report that case**. Preserve Phase 2's accepted calculator and source history; don't blanket-exclude the 981 session-unverified paired timer scopes or add generalized diagnostic gates.
- The four preflight tests and 416 total prior tests were run **before feature implementation**; do not accept PC-01 without complete curve/math/cache/browser and archival verification.

## Final acceptance disposition — 2026-10-11

**PC-01 accepted. HARD — Analyst Gate 1 and HARD — Owner Gate 2 cleared.** The Analyst inspected the pushed source-selection, observed-MMP-window implementation, verified/unverified timer treatment, profile/cache publication and historical period envelope, together with Dex's reported [implementation](../reports/PC-01/implementation.md), [independent numerical verification](../reports/PC-01/verification.json), [test/browser counts](../reports/PC-01/checks.json), [runtime](../reports/PC-01/runtime.json), [concurrent-build checks](../reports/PC-01/build-availability.json) and [accepted-model comparison](../reports/PC-01/accepted-behavior.json). The Owner reviewed the feature and explicitly said **"I'm pleased with this. I think we can close it."**

Performance retains the accepted 20-Minute History by default and adds two selectable period curves. Activity Review defaults to **the selected ride versus its own preceding 42 days**, excludes the selected ride and later rides, and exposes exact duration/source attribution. The documented JIT §13 timer rule and honest unavailable states remain. Dex reported **440 passing Python tests, 1,959 browser checks, 122,112 independently verified curve results, exact 1,022 native and seven API 20-minute parity checks**, stable fixed-clock accepted Performance/Training State/Plan, all 20 original source tables and **1,422 source artifacts preserved**, and no original FIT/TCX/GPX modifications. The Analyst did not rerun the private local store; reviewed committed code and reproducible source-neutral evidence.

**Accepted practical limitation:** forced full-history profile build takes about 23 seconds and may cause CPU contention (reported concurrent-page slowdown), while incremental/cached lookups are faster. Computed anchors are approximately 7% apart beyond 30 seconds, not every duration; between-anchor visual segments are explicitly not exact extra computations. The initial cohort excludes untrusted outdoor power. These limits are documented and acceptable for a private single-rider v1.

This final acceptance **supersedes the preceding pre-implementation-only clarification and pending-gate text**; earlier sections remain as historical requirements. Phase 6 is still deferred and is not authorized by PC-01 closeout.
