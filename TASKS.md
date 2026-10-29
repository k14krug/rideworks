# TASKS.md

## Status values

```text
pending
in_progress
blocked
done
```

Only one implementation/research task should normally be `in_progress`.

---

## Planned work

### STRAVA-001 — Inventory latest Strava bulk export

**Status:** done

**Purpose:** Inspect Ken's latest local Strava bulk export and produce a compact, reproducible inventory that tells us what source data actually exists before detailed import design begins.

**Scope summary:**

* inspect the export structure and `activities.csv`
* inventory activity-file formats and historical coverage
* identify associations, obvious gaps, and unusual cases useful for later investigation
* produce compact machine-readable and human-readable outputs suitable for Analyst review
* keep the raw export and personal activity archive out of Git

**Acceptance:** See `docs/tasks/STRAVA-001.md`.

**Dependency:** Workflow bootstrap complete.

---

### STRAVA-002 — Deep inspect representative activity files

**Status:** done

**Purpose:** Deeply inspect the STRAVA-001 diagnostic candidates and compare source-file evidence with Strava CSV metadata before making importer or historical-data-model decisions.

**Scope summary:**

* parse the 23 candidate FIT/TCX/GPX files at a diagnostic level
* compare source-file evidence with corresponding `activities.csv` rows
* characterize signal availability, timing behavior, device/session/lap metadata, and power provenance evidence
* characterize the 13 CSV rows without filename references
* keep raw activity streams and personal source files out of Git

**Acceptance:** See `docs/tasks/STRAVA-002.md`.

**Dependency:** STRAVA-001 complete.

---

### STRAVA-004 — Strava activity-stream enrichment and FIT comparison

**Status:** done

**Purpose:** Validate current Strava activity streams against preserved FIT evidence on the four accepted overlap rides, then—only if the evidence supports it—use bounded post-export Strava stream enrichment to power honest Activity Review graphs for API-only rides.

**Scope summary:**

* fetch only time/watts/heartrate/cadence/moving streams for the four live overlap rides first
* compare Strava stream metadata, timing and values against preserved FIT evidence
* experimentally compare best-20 only when API timing independently satisfies accepted complete-window semantics
* preserve API stream provenance distinctly from FIT/native-file evidence
* keep FIT-backed review authoritative when a supported FIT exists
* allow API-only post-export rides to gain stream-backed power/HR charts when evidence is adequate
* apply Owner-approved `virtual-power-evidence-v2` with file-backed power precedence and strict API fallback eligibility
* automatically converge Performance after normal Sync now; keep the banner for unresolved freshness/failure
* perform only bounded recent/post-export stream access; no historical stream harvest

**Current Owner correction:** adopt `virtual-power-evidence-v2`, admit only validated API-only Virtual Ride power streams under strict evidence rules, preserve file precedence, and make Sync now automatically rebuild Performance only when current history is pending/stale. The Performance banner becomes an exception/failure state rather than a routine second step.

**Acceptance:** See `docs/tasks/STRAVA-004.md`.

**Allowed invocation:** `/TASK` or `/AUTOTASK`.

**Acceptance result:** Owner and Analyst accepted PR #18; merged to `main` as `e7920493dfadbb5f15b0352315cce433f7991ecd`. `virtual-power-evidence-v2` retains all 1,022 file-backed eligible results unchanged and adds 5 validated API-only Virtual Rides for **1,027 eligible / zero pending**. Sync now automatically converges Performance when needed; eligible API rides receive six-week context; failure/retry remains explicit. 253 full / 57 focused Strava / 38 focused Performance tests plus Chromium acceptance passed. Phase 3 did not begin.

**Dependency:** Phase 2 accepted / complete.

---

### STRAVA-003 — Historical data-coverage census

**Status:** done

**Purpose:** Quantify the source-data characteristics discovered by STRAVA-001/002 across the complete Strava export so later historical-data design is grounded in prevalence, not a 23-file sample.

**Scope summary:**

* account for all 1,434 CSV rows and attempt all 1,421 referenced activity files
* quantify FIT/TCX/GPX signal and structural coverage by year and activity cohort
* quantify Ride and Virtual Ride evidence combinations relevant to later historical analysis and estimated-power research
* keep source record power, source summary power, and Strava CSV power metadata distinct
* quantify recording/timestamp characteristics and parse/outlier conditions
* produce a durable findings document separating evidence, unknowns, implications, and candidate design decisions

**Acceptance:** See `docs/tasks/STRAVA-003.md`.

**Dependency:** STRAVA-002 complete.

---

### DESIGN-001 — Durable activity and provenance model

**Status:** done

**Purpose:** Establish the conceptual model for durable Activity identity, source evidence, provenance, historical state, derivations, and conservative source reconciliation before storage/import implementation design.

**Decision:** See `docs/design/DESIGN-001.md`.

**Dependency:** STRAVA-003 complete.

---

### DESIGN-002 — Source-centered storage and import representation

**Status:** done

**Purpose:** Translate DESIGN-001 into the simplest practical logical storage/import representation while preserving immutable source evidence, typed normalized extraction, native timing, historical context, and reproducible derivations.

**Decision:** See `docs/design/DESIGN-002.md`.

**Dependency:** DESIGN-001 complete.

---

## Phase 1 — Useful single-ride review

**Status:** accepted / complete — P1-03 accepted at Gate 2 and PR #12 merged on 2026-10-04.

**Acceptance contract:** `docs/PHASE_1_ACCEPTANCE.md`

### P1-01 — Durable single-FIT activity import

**Status:** done

**Purpose:** Import the Phase 1 representative FIT as a durable application-owned Activity + Source, preserve the original artifact unchanged, and persist the minimum typed source evidence/native streams needed by Phase 1.

**Scope summary:**

* use the representative activity identified by the Phase 1 acceptance contract
* create durable application-owned Activity identity
* associate the FIT Source and preserve original artifact/integrity evidence
* extract typed source/session/stream evidence without destructive canonicalization
* preserve native timing
* support re-extraction without reacquiring the original
* establish a clean RideWorks application/runtime boundary with no compatibility obligation to the retired Strava application; legacy application code may be ignored or removed if that is simpler

**Acceptance:** See `docs/PHASE_1_ACCEPTANCE.md` and `docs/tasks/P1-01.md`.

**Dependencies:** DESIGN-001, DESIGN-002, and Phase 1 acceptance contract complete.

---

### P1-02 — Single-ride analysis core

**Status:** done

**Purpose:** Produce the trusted analytical inputs needed by the Phase 1 activity-review experience.

**Scope summary:**

* expose the required FIT-backed summary evidence
* expose native power and heart-rate streams
* define the narrow complete-window semantics for the representative ride and calculate reproducible best 20-minute power as an application derivation
* independently verify the 20-minute result without using the production calculation as its own oracle
* keep source summaries and application derivations distinct
* provide verification suitable for later UI consumption

**Acceptance:** See `docs/PHASE_1_ACCEPTANCE.md` and `docs/tasks/P1-02.md`.

**Dependency:** P1-01 complete.

---

### P1-03 — Activity review experience and Phase 1 acceptance

**Status:** done

**Purpose:** Turn the Phase 1 evidence and analysis into the first useful rider-facing post-ride review experience.

**Scope summary:**

* activity identity/header
* required summary metrics
* native-timing power and heart-rate review
* best 20-minute result
* practical provenance/inspectability details
* implement `docs/mockups/activity-review.png` as the preferred layout/visual reference, using only capabilities genuinely available in Phase 1
* use the **RideWorks** product name consistently in the user-facing application shell
* integrate the settled RideWorks branded application icon/mark assets from the parallel branding workstream and obtain Owner visual approval
* define the narrow first user journey: start RideWorks, open/select the imported ride, reopen it after restart, and use appropriate units/timezone/chart interaction
* Owner visual/usability acceptance against both the representative ride and the approved mockup

**Acceptance:** `docs/PHASE_1_ACCEPTANCE.md` and `docs/tasks/P1-03.md`.

**Dependency:** P1-02 complete.

---

## Phase 2 — Historical context and performance history

**Status:** accepted / complete — P2-01 through P2-05 accepted; PR #17 merged on 2026-10-05.

**Acceptance contract:** `docs/PHASE_2_ACCEPTANCE.md`

### P2-01 — Historical Strava-export import and enrichment

**Status:** done

**Purpose:** Import the complete known Strava-export activity history through one durable, idempotent RideWorks workflow, preserving real source titles, CSV evidence, referenced FIT/TCX/GPX artifacts, CSV-only activities, and conservative source associations.

**Scope summary:**

* account for all 1,434 known export rows
* import/preserve all 1,421 referenced activity artifacts
* retain the 13 CSV-only activities without fabricating streams
* preserve actual source activity titles with provenance
* support FIT/TCX/GPX production import for the known export envelope
* migrate the accepted Phase 1 store safely
* enrich the already-imported Phase 1 representative Activity rather than duplicating it
* make reruns idempotent and failures explicit
* expose a source-aware history read boundary for later Phase 2 work

**Acceptance:** `docs/PHASE_2_ACCEPTANCE.md` and `docs/tasks/P2-01.md`.

**Allowed invocation:** `/TASK` or `/AUTOTASK`.

**Acceptance result:** accepted by Analyst on PR #13 and merged to `main` as `57c00ae396bfb1e9c2c4c72ff42c5628afda9940`. Complete 1,434/1,421/13 seeded acceptance and restart/idempotent rerun passed.

**Dependency:** Phase 1 accepted; Phase 2 acceptance contract complete.

---

### P2-02 — Scalable Activities browser

**Status:** done

**Purpose:** Make the full imported history practical to browse rather than rendering an unbounded list.

**Scope summary:**

* newest-first bounded pagination
* title search
* activity type/subtype filtering
* practical date filtering
* useful sorting
* source title presentation with derived fallback when necessary
* stable Activity Review navigation
* preserve the approved RideWorks visual character without recreating irrelevant Strava management features

**Acceptance:** `docs/PHASE_2_ACCEPTANCE.md` and `docs/tasks/P2-02.md`.

**Acceptance result:** Owner and Analyst accepted the corrected browser on PR #14; merged to `main` as `683c9880bb0b6ed1cd9569a58be61093ec2cce0e`. 142 tests and full-history HTTP/restart/Chromium checks passed, including multiple timezones and single-line local date/time.

**Allowed invocation:** `/TASK` or `/AUTOTASK`.

**Dependency:** P2-01 complete.

---

### P2-03 — Trusted 20-minute performance history

**Status:** done

**Purpose:** Build the first trusted longitudinal performance view from eligible Virtual Ride native source-power evidence.

**Scope summary:**

* reuse accepted `best-average-power-v1` complete-window semantics
* derive durable/versioned best-20 history from eligible Virtual Ride native streams
* exclude outdoor Ride power from the trusted Phase 2 trend
* never substitute CSV/source-summary watts for missing native streams
* present chronological 20-minute-power history with links to contributing activities
* make eligibility/provenance inspectable

**Acceptance:** `docs/PHASE_2_ACCEPTANCE.md` and `docs/tasks/P2-03.md`.

**Allowed invocation:** `/TASK` or `/AUTOTASK`.

**Acceptance result:** Owner and Analyst accepted the final Performance experience on PR #15; merged to `main` as `4f1a58d39177887e965ddd1a74db95c62c17e0b0`. 170 full / 28 focused tests passed; all 1,434 Activities accounted for and all 1,022 eligible trusted results independently verified.

**Dependency:** P2-02 complete.

---

### P2-04 — Six-week historical context in Activity Review

**Status:** done

**Purpose:** Put an eligible ride's best-20 result into recent historical context.

**Scope summary:**

* compare current eligible best-20 with the highest eligible result in the preceding 42 days
* exclude the current activity from its own baseline
* show unavailable when no eligible baseline exists
* keep presentation neutral rather than assuming higher/lower is inherently good/bad
* connect Activity Review to the trusted Performance history
* no manual pairwise ride-comparison feature

**Acceptance:** `docs/PHASE_2_ACCEPTANCE.md` and `docs/tasks/P2-04.md`.

**Allowed invocation:** `/TASK` or `/AUTOTASK`.

**Acceptance result:** Owner and Analyst accepted PR #16; merged to `main` as `16ef375434700ab7d2b5fb3a5c2cae000e049c12`. 186 tests passed; all 1,022 eligible comparisons independently verified (1,012 with prior baseline / 10 unavailable), with no archive/source reprocessing.

**Dependency:** P2-03 complete.

---

### P2-05 — Incremental Strava synchronization

**Status:** done

**Purpose:** Bring post-export activities and useful Strava metadata into RideWorks through a normal forward-looking sync path.

**Scope summary:**

* current Strava OAuth/API behavior re-verified from authoritative documentation in the JIT
* normal incremental/forward sync rather than historical bulk API harvesting
* user-invoked sync is acceptable for the first private single-rider implementation
* create new Activities or conservatively enrich existing local/FIT Activities
* retain Strava source identity/title/type/useful metadata with provenance
* keep credentials/tokens local and out of Git
* obey current rate-limit/terms/webhook obligations without enterprise sync infrastructure

**Acceptance:** `docs/PHASE_2_ACCEPTANCE.md` and `docs/tasks/P2-05.md`.

**Allowed invocation:** `/TASK` or `/AUTOTASK`.

**Acceptance result:** Owner and Analyst accepted PR #17; merged to `main` as `e78c8a6c2de4f4e21aaa2937ae33d1e011901947`. 219 tests passed; live sync created 7 post-export Activities, enriched 4 overlaps with no duplicates, restart reruns were idempotent, and explicit rebuild cleared 11 pending Performance results.

**Dependency:** P2-04 complete.

---

## Follow-up work

Phases 1–5 v1 and STRAVA-004 are accepted and complete. Adaptive Phase 6 is deferred by Owner choice. **PC-01 power-duration curves** are implemented and locally verified under `/AUTOTASK PC-01`, ready for HARD — Analyst Gate 1 review on draft PR #28. Not accepted.

Manual pairwise ride-to-ride comparison is not a Phase 2 requirement. It remains an optional future interaction if a concrete use case emerges.

Outdoor power remains preserved source evidence but is excluded from the trusted Phase 2 performance trend. Outdoor estimated-power reconstruction remains separate future work.

Phase 3 must not begin automatically after Phase 2.


---

## Phase 3 — Useful dashboard

**Status:** accepted / complete — P3-01 accepted; PR #19 merged on 2026-10-08.

**Acceptance contract:** `docs/PHASE_3_ACCEPTANCE.md`

### P3-01 — Useful dashboard and annual mileage goal

**Status:** done

**Purpose:** Make RideWorks useful before opening an individual Activity, centered on annual cycling mileage progress, recent rides and already-accepted Performance-v2 evidence.

**Owner-set decisions:**

* Virtual Ride mileage counts toward the annual cycling mileage goal.
* Outdoor Ride mileage counts.
* File-backed distance is preferred; current Strava API distance is the fallback.
* CSV distance with unspecified units is not guessed.
* Annual mileage is the first narrow goal; do not build a generic goal engine.
* No Fitness Score, Training Load, Next Workout, adaptive plan or full power curve in Phase 3.

**Scope summary:**

* Home dashboard at `/`; Activities browser moves to `/activities`
* current-year annual mileage goal setting in Settings
* YTD goal progress and calendar pace
* trailing-7-day mileage
* recent cycling Activities
* current 42-day best and latest eligible 20-minute result
* compact mileage and Performance visualizations
* deterministic explainable insights only
* preserve STRAVA-004 Performance-v2 and sync behavior

**Acceptance:** `docs/PHASE_3_ACCEPTANCE.md` and `docs/tasks/P3-01.md`.

**Allowed invocation:** `/TASK P3-01` or `/AUTOTASK P3-01`.

**Acceptance result:** Owner and Analyst accepted PR #19; merged to `main` as `5e5bceed0244ae1fa64ec3a45a101f49be5b8f15`. Final dashboard uses three top cards (Recent Mileage, Current 42-day best, Latest eligible 20-minute ride), annual-goal Mileage Progress with actual weekly bars and separate needed-mi/week line, Recent Activities Avg Pwr, and reconciled YTD mileage. The bounded eight-ID historical summary repair added 112.984110296 mi, producing 1,631.195462250 mi YTD / 120 contributors / zero distance unavailable while preserving originals, the 2,200-mi goal, Performance-v2 and normal forward sync. 285 full / 24 focused dashboard tests plus Chromium, independent SQL/Decimal, restart, sync/failure recovery, integrity/FKs and artifact-preservation checks passed.

**Dependency:** Phase 2 and STRAVA-004 accepted / complete.

Phase 4 is now explicitly Owner-authorized. Phase 5 must not begin automatically.


---

## Phase 4 — Training state

**Status:** **done — accepted 2026-10-10.** P4-01 model evaluation and P4-02 rider-facing Training State implementation accepted. Phase 5 is the next design/planning area; no new implementation task has begun.

**Acceptance contract:** `docs/PHASE_4_ACCEPTANCE.md`

### P4-01 — Training-state model evaluation and athlete-state inventory

**Status:** done

**Purpose:** Evaluate transparent training-load/current-state models against the rider's actual RideWorks history before implementing a production Fitness/Fatigue/Form model.

**Scope summary:**

* inventory historical FTP/weight/HR-state evidence and missing periods;
* census eligible power/HR/duration/work coverage;
* compare classic TSS/CTL/ATL/TSB-style baseline with simpler transparent short/long workload;
* evaluate HR-derived fallback only when required HR reference state exists;
* keep power/HR/external-load evidence classes distinct;
* keep outdoor suspect/estimated power out of the first load baseline;
* compare model behavior against real training periods and Performance-v2 history without overfitting;
* recommend the first RideWorks training-state model in DESIGN-003;
* no production state UI/schema/planning in P4-01.

**Acceptance:** `docs/PHASE_4_ACCEPTANCE.md` and `docs/tasks/P4-01.md`.

**Allowed invocation:** `/TASK P4-01` only (explicit JIT Execution Control).

**Owner continuation — 2026-10-09:** Initial research PR #23 is awaiting revised P4-01 evaluation. Owner provided 66 historical Strava FTP entries (private screenshot), approved each date as effective through the next entry, and authorized comparing normalized stress with workload-first using a review of recording gaps and duration semantics. Preserve the original retained-evidence census, use the Owner-approved publicly committed FTP CSV as the research source, and return to HARD — Owner after revised model comparison. This authorizes P4-01 research, not P4-02 implementation or Phase 4 acceptance.

**Owner continuation — Sauce experiment, 2026-10-09:** Before final model decision, compare pinned Sauce-for-Strava active-time/gap-correction logic with strict full-timer and observed-only 600-second segment stress. Test deterministic injected gaps against complete reference recordings and assess disagreement/coverage on real interrupted rides. Distinguish derived estimates from observed power; retain hard Owner gate, unchanged production data and Performance-v2, and no P4-02 implementation. See JIT §15 and PR #23 Analyst source review.

**Owner model/policy decision — 2026-10-09:** APPROVED separate 7-/42-day observed work and evidence-scoped stress; FIT-only internal missing-power correction where every gap is <=15 seconds and total missing time <=1% of the recorded interval; no API gap correction yet; validated timer stop/start events govern pauses and NP resets. Use calculated / estimated / partial / unavailable evidence labels with explicit omissions. The Owner's design gate is resolved, superseding the earlier tentative 5-second rule. Dex must reconcile DESIGN-003 and reports on existing PR #23, rerun relevant checks, and stop at **HARD — Analyst** for acceptance. P4-01 remains in progress; no P4-02 work or merge authorized. See JIT §16.

**Reconciled for Analyst review:** DESIGN-003 reflects the approved 15-second FIT-only rule and pause precedence. Verified subset: 131 FIT intervals (prior 133 included two API). Boundary metadata correction: one candidate has corroborating timer/session metadata; no corrected whole-session result is verified. 311 tests, 52 Node assertions and preservation checks pass. Stop at HARD — Analyst; task remains in_progress.

**Analyst acceptance — 2026-10-09:** P4-01 research/design **accepted** after final Owner-approved 15 s / 1% **FIT-only** reconciliation (131 FIT intervals; two API candidates excluded). Corrected boundary statement: one FIT candidate has corroborating timer/session metadata, but no new corrected whole-session stress result verified. 311 reported Python tests, 52 Node assertions, independent numerical/report verification and original-data preservation passed. [PR #23 review](https://github.com/k14krug/rideworks/pull/23#pullrequestreview-5475713826). Accepted DESIGN-003 is research/design, not production. No P4-02 JIT/implementation, Phase 5 or 6 started; Phase 4 remains active pending separately authorized implementation.

**Dependency:** Phase 3 accepted / complete.

### P4-02 — Longitudinal training-state experience

**Status:** **done — Analyst Gate 1 and Owner Gate 2 accepted 2026-10-10.** Training State v4 is approved, including the estimated session-power selector and Form initially unchecked. [Acceptance record](https://github.com/k14krug/rideworks/pull/24).

**Purpose:** Produce a useful, repeatable Fitness/Fatigue/Form view for this recreational rider, grounded in qualified measured-power stress, a practical approximate HR-based fallback, the approved dated FTP history, and explicit source quality.

**Owner-confirmed design context:** [P4-02 training-state direction](docs/design/P4-02-training-state-direction.md), read together with accepted [DESIGN-003](docs/design/DESIGN-003-training-state-model.md) and the [Phase 4 acceptance contract](docs/PHASE_4_ACCEPTANCE.md). The October 9 follow-on conversation supports HRSS-style outdoor fallback and a 42-/7-day interactive longitudinal chart. The Owner subsequently approved the **pragmatic Elevate-style unscored-ride numerical contribution of zero** (retain original missing-stress evidence), **prior-day Form**, a **zero initial seed**, and **no v1 projections/fixed training zones**. The Owner approved using **58 bpm resting / approximately 158 bpm max** and modeled **143 bpm threshold** as **explicit retrospective assumptions** for older rides without dated HR evidence, plus prioritizing adequately covering HR stress over materially partial power. The JIT specifies a simple versioned fixed-coefficient HRSS recipe; these inputs are assumptions, not historical measurements. This is **not** an implementation authorization.

**Acceptance evidence:** [P4-02 final implementation verification](reports/P4-02/session-power-implementation.md) confirms actual selected Elevate-style estimated session PSS on the 2026-10-07 structured interval workout (instead of old HR-only selection), same-day Fitness/Fatigue and next-day Form response, preserved 2026-09-16 outdoor HR stress, all candidate/source provenance, and 28 ride source-selection improvements. The Owner accepted the visible result and requested Form initially unchecked, which is implemented and browser-verified. Dex reported **383 Python tests, 506 general / 614 representative browser assertions, 1,418 fresh/cache parity checks, source/FTP/benchmark preservation and unchanged Performance**. Analyst reviewed the committed code and safe aggregate evidence; no additional private raw-data import or future-planning implementation is part of this task. Phase 4 acceptance applies to the v1 feature with its documented incomplete-data limitations.

**Dependency:** P4-01 accepted; P4-02 accepted and complete.

### Phase 5 — Workout intent, outcome, and initial planning

**Status:** **done — Phase 5 v1 accepted 2026-10-10** with P5-01 accepted at HARD — Analyst Gate 1 and Owner Gate 2. [PR #26](https://github.com/k14krug/rideworks/pull/26). Later Phase 6 adaptation is separate and not started.

**Accepted scope:** [Owner-approved rolling training direction](docs/design/P5-01-rolling-training-plan.md) and [Phase 5 acceptance](docs/PHASE_5_ACCEPTANCE.md). Home and Activity Review display the next *future* ride after one is already completed today; Plan shows daily recommendations and three upcoming hard milestones. Never recommend Rest/no ride. Synced skipped past dates count as assumed rest *only for planning*, not invented completed rides. Two hard days/seven is a soft guideline with a limited disclosed exception. No Zwift file management or race discovery.

### P5-01 — Rolling Training Advisor (Home, Plan and outcome context)

**Status:** **done — accepted 2026-10-10**, after Analyst review of PR #26 v2 code/evidence and Owner positive running-app review. HARD — Analyst Gate 1 and HARD — Owner Gate 2 cleared. [PR #26](https://github.com/k14krug/rideworks/pull/26), [issue #25](https://github.com/k14krug/rideworks/issues/25).

**Purpose:** Deliver explainable next-ride recommendations with Race / Threshold / VO2 / Z2 / Easy / Recovery rotation, current goal-aware coaching context, two-date post-hard recovery, rolling hard-day frequency guardrail, handling of unexpected rides and skipped days, and a dedicated Plan extending through three future hard sessions.

**Scope and acceptance:** [P5-01 JIT](docs/tasks/P5-01.md) and [Phase 5 acceptance](docs/PHASE_5_ACCEPTANCE.md). Include Home/Plan consistent primary next recommendation, an honest initial Activity Review connection, minimal legs-heavy and ambiguous-classification handling, and real/synthetic behavioral checks. Preserve P4-02 Training State, dated FTP and original source records.

**Allowed invocation:** `/TASK P5-01` or `/AUTOTASK P5-01`; HARD — Analyst Gate 1 and HARD — Owner Gate 2. Prepare/push review evidence before acceptance; no implied background execution.

**Final acceptance:** [JIT §10](docs/tasks/P5-01.md) corrections and the [editable Plan mockup](docs/mockups/plan-rotation-v2.html) were implemented. Actual October 10 synced Recovery now advances the shared Home/Plan/Activity Review next ride to October 11 Race. Before the ride, an appropriate hard effort was eligible after two no-ride dates; limited third-in-seven exceptions are explained. Three hard milestones, compact daily rotation, optional quick race confirmation, heavy-legs feedback and distinct intent/actual semantics verified. [Final report](reports/P5-01/review-followup.md): Dex reported **412 Python tests, 161 browser assertions**, with original sources, historical FTP, Training State and Performance preserved. Analyst reviewed the pushed code and aggregate/browser evidence; Owner said the updated P5-01 looked good. Remaining source ambiguity stays disclosed rather than presented as definitive exercise classification.

### Phase 6 — Adaptive planning

**Status:** deferred at Owner direction (2026-10-10) — adaptive planning remains a possible future phase, but the Owner wishes to skip it for now. No Phase 6 task/JIT/invocation.

### PC-01 — Power-duration curves (Performance + Activity Review)

**Status:** **done — accepted 2026-10-11**, HARD — Analyst Gate 1 and HARD — Owner Gate 2 cleared following source/code/evidence review and the Owner's positive assessment. [PR #28](https://github.com/k14krug/rideworks/pull/28), [issue #27](https://github.com/k14krug/rideworks/issues/27). [Final report](reports/PC-01/implementation.md): 440 passing Python tests, 1,959 browser checks, 122,112 independent duration results, exact 1,022 native / seven API best-20 parity, 20 original source tables / 1,422 artifacts intact and accepted Performance/Training State/Plan preserved.

**Purpose:** Extend currently accepted 20-minute Performance to source-qualified maximal mean-power bests over short and long durations, with a Performance Power Curve mode comparing two independently selectable periods and a single-activity curve versus historical prior-six-week bests. Preserve first-class existing 20-minute history and Activity Review.

**Controlling artifacts:** [PC-01 design](docs/design/PC-01-power-duration-curves.md); [PC-01 acceptance](docs/POWER_CURVE_ACCEPTANCE.md); [editable visual reference](docs/mockups/power-curve-v1.html); [Analyst JIT PC-01](docs/tasks/PC-01.md). Owner's default is historic [ride start − 42 × 24h, ride start), excluding the selected ride and later rides. Mockup values are synthetic, not evidence.

**Final disposition:** Delivered both interactive Power Curve views, cached reproducible source-qualified observed MMP, and historical prior-six-week ride comparison. JIT §13's timer evidence policy and old 20-minute parity are verified. The Analyst accepted the technical gate and the Owner accepted the running feature. Both gates are closed, PR #28 authorized to merge. Existing caveats about complete rebuild time and nonqualifying sources remain visible. No Phase 6 start.

### AR-UI-01 — Activity Review visual redesign

**Status:** **done — accepted 2026-10-11** at HARD — Analyst Gate 1 and HARD — Owner Gate 2 after final compact-header Owner review. [PR #30](https://github.com/k14krug/rideworks/pull/30), [issue #29](https://github.com/k14krug/rideworks/issues/29).

**Scope:** Make the existing **Activity Review / Ride Details**, not the Activities list, visually follow the approved concept. New responsive hero and metrics, larger Power/HR chart, contextual Ride Summary/Workout Context/Current Next Ride, full-width existing PC-01 Power Curve and best-effort comparisons, with complete source/calculation disclosures in readable sections. Keep existing sources, chart calculations, source-policy and Plan behavior. Define candidate reusable design tokens but **do not** restyle other pages yet.

**Controlling artifacts:** [AR-UI-01 approved design](docs/design/AR-UI-01-activity-review-redesign.md), [HTML concept](docs/mockups/activity-review-ui-concept.html), [implementation JIT](docs/tasks/AR-UI-01.md). Historical `activity-review.png` remains background, now superseded for the specific Ride Details layout by this approved concept.

**Owner follow-up — 2026-10-11:** Power Curve appears above Workout Context and Current next ride. Implemented and verified across desktop/mobile on the existing draft PR; accepted data and Plan behavior are unchanged.

**Owner compact-header follow-up — `/TASK AR-UI-01`, 2026-10-11:** Remove duplicate upper-right jump buttons and divider; reduce header padding/title/gradient treatment; consolidate redundant type/subtype wording; retain all four aligned metrics and five section links, with compact mobile 2×2 metrics. Target desktop header plus section navigation 190–220px where content permits. Preserve source modes, analysis, charts, controls and provenance. Before/after desktop/mobile comparison and regression verification complete on the existing draft PR; desktop header/navigation measures 212–217px in real source modes. Returned for review without merging.

**Execution and gates:** Start in Dex with `/TASK AR-UI-01` or `/AUTOTASK AR-UI-01` after refreshing `main`. Dex implements on a draft PR, checks native FIT, Strava API/retained stream, thin/unsupported and outdoor views, responsive desktop/320px mobile, keyboard/touch and preservation of PC-01/20-minute/Plan/evidence. **HARD — Analyst Gate 1** technical/UI review, then **HARD — Owner Gate 2** running visual acceptance. No merge/claim of completion before both. Phase 6 stays deferred.

**AR-UI-01 final acceptance evidence:** [Implementation report](reports/AR-UI-01/implementation.md): 445 Python tests, 24,304 Chromium checks, 212–217px desktop header/navigation, chart raised 149–195px, 27 fixed-clock source-mode parity comparisons and all source artifacts/accepted calculations preserved. Owner said “This looks good.” Dashboard redesign is a separate forthcoming task; Phase 6 deferred.

### HOME-UI-01 — RideWorks visual refinement

**Status:** **done — accepted 2026-10-12 at HARD — Analyst Gate 1 and HARD — Owner Gate 2.** [PR #32](https://github.com/k14krug/rideworks/pull/32) approved for merge and [issue #31](https://github.com/k14krug/rideworks/issues/31) closure. The full Owner-directed cross-page visual pass covers Activities list, both Performance views, Training State, Plan and Settings, alongside the refined Home and accepted Activity Review.

**Scope:** Compact readable headers, shared scoped palette/14px main cards, restrained blue left edges, full chart space, responsive browsing/schedule/forms and inspectable source evidence. Preserve the refined Home card order and all accepted activity, Performance/Power Curve, Training State, Plan, Settings and mileage/goal behavior. No new calculations, models or Phase 6 work.

**Controlling resources:** [HOME-UI-01 JIT](docs/tasks/HOME-UI-01.md), [responsive HTML concept](docs/mockups/home-dashboard-ui-concept.html), [AR-UI-01 accepted design](docs/design/AR-UI-01-activity-review-redesign.md).

**Final acceptance evidence:** 446 Python tests and 15,435 Chromium assertions passed, including all five viewports and full Activities, Performance, Training State, Plan and Settings interactions. Six fixed-clock cases preserve 36 page states, models, all 26 tables, 1,422 source originals and approved FTP/Elevate references. [Implementation report](reports/HOME-UI-01/implementation.md). Analyst reviewed committed code/evidence (not the private local store); Owner viewed the integrated running app and said **“I like the way things look now”**, clearing final visual acceptance. **Next focus is production data-store transition planning**, not another UI change or Phase 6.


### OPS-01 — One authoritative RideWorks data store

**Status:** **done — Analyst Gate 3 accepted 2026-10-12; Owner Gate 4 accepted for the migration scope 2026-10-12.** [PR #34](https://github.com/k14krug/rideworks/pull/34), [issue #33](https://github.com/k14krug/rideworks/issues/33). Owner reports production setup completed and expressly directs that the migration changes be brought into `main`. Nginx/public-host and environment-variable follow-ups are separate work, not acceptance claims for the HTTP deployment boundary.

**Purpose:** One everyday SQLite store at repository-root `data/`, using the existing non-Flask application, trusted originals, provenance, historical metrics and private Strava state. This is the Owner's final location decision, superseding older outside-repository recommendations.

**Controlling resources:** [OPS-01 JIT §8](docs/tasks/OPS-01.md), [design background](docs/design/OPS-01-production-data-home.md).

**Delivered:** Approved current-use source copied consistently and verified once: 1,443 Activities, 1,422 originals, identities, user state, sync and caches intact. Project-root default independent of CWD, root `/data/` ignore, missing-store guard, active-store Settings display, executable/desktop launcher at port 8766. Removed 85 obsolete test stores and 15 known test-run remainders (~19.4 GiB); Owner follow-up removed another 15 retired research/empty folders and two logs (~1568.7 MiB); original inputs retained.

**Verification / acceptance:** [Promotion report](reports/OPS-01/promotion.md): 61 focused tests and 26 promoted-store browser assertions, six main routes and restart from another CWD passed. Stage A 453/640 evidence retained. Analyst Gate 3 accepted; Owner says the production migration is complete for practical purposes and directs closing/merging OPS-01. The old `local_data/p2-05-review` source was preserved for rollback in the implementation; repository merge cannot remove it from the Owner's machine. Any final private-local cleanup is a separate local action. Existing backups remain Owner-managed. No Flask conversion, repeated multi-store audit, new backup system or Phase 6.

**Post-deployment follow-up:** Nginx-forwarded public `Host` is currently rejected with HTTP 403; Settings/Plan Origin checks and Strava OAuth redirect also assume loopback. Rename `FLASK_RUN_PORT` to `RUN_PORT` and `FLASK_DEBUG` to `DEBUG` throughout runtime/config/docs/tests. These changes are not implemented by OPS-01 and must not be described as shipped.


### OPS-02 — nginx proxy compatibility and framework-neutral runtime settings

**Status:** **done — implementation accepted by Analyst and Owner authorized immediate merge to `main` on 2026-10-12.** [PR #36](https://github.com/k14krug/rideworks/pull/36), [issue #35](https://github.com/k14krug/rideworks/issues/35). Actual home-LAN nginx deployment and Strava LAN callback-domain support remain unverified; they are not represented as passed acceptance tests.

**Purpose:** Support the Owner's HTTP-only private home-LAN nginx reverse proxy using a configured public origin and use `RUN_PORT`/`DEBUG` in place of misleading Flask-named runtime keys.

**Acceptance:** [OPS-02 JIT](docs/tasks/OPS-02.md), [issue #35](https://github.com/k14krug/rideworks/issues/35). The Analyst accepted reviewed code at PR head `8cf79e1` after inspection and Dex's 93 focused / 474 regression test report. The Owner explicitly directed merging to `main` without treating live deployment as a merge gate; this supersedes the JIT's earlier Owner deployment gate for **merge timing only**. Keep backend loopback-only and strict Host/Origin/nonce checks. Separate from accepted OPS-01.

**Implementation evidence:** [Report](reports/OPS-02/implementation.md): 93 focused and all 474 regression tests passed. HTTP LAN hostname/IP, default/custom external ports, strict Host/Origin/nonce checks and fake browser OAuth verified; backend remains loopback-only. `RUN_PORT`/`DEBUG`, example and nginx/systemd documentation updated. Actual private deployment and provider callback-domain acceptance have not been tested; no production data or live secrets were changed. Verify normal HTTP nginx access and Settings/Plan actions after deploying the merged code, and investigate provider callback restrictions if reconnecting Strava is ever needed.


### FTP-01 — Database-owned FTP history and editable 20-minute chart

**Status:** **done — Owner final Gate 4 acceptance 2026-10-17.** [Merged PR #41](https://github.com/k14krug/rideworks/pull/41) at `cc3acc5527230bb88405b28dd1378fe6d41cde34`; [issue #37](https://github.com/k14krug/rideworks/issues/37); [FTP-01 JIT](docs/tasks/FTP-01.md). The Analyst accepts the completed, Owner-approved task. All Owner gates are complete for the **main development RideWorks application** on port 8765.

**Delivered:** One SQLite date-effective FTP timeline with 66 approved starting entries, equal-status later entries, manual and ride-derived additions between historical dates or before the first known FTP date, and explicit unknown/timezone-uncertain comparison handling. Performance FTP History includes smaller dots and a draggable range navigator. Training State, Planning, Home, and Activity Review consume shared date-effective FTP with correctly invalidated/recalculated caches. The three FTP CSVs and obsolete loader were retired from the activated release.

**Evidence:** Gates 1/2 and Gate 3 refinements passed separate fresh-context Astra technical reviews. Reconciled release passed 494 Python tests and 107 disposable-browser assertions; earlier focused Astra checks passed 88 tests and 21 browser assertions. The Owner-reported controlled development cutover completed with schema 11, 66 FTP entries/revision 1, unchanged 1,444 activities, 2,885 Performance history records, 22 Strava API activities, 24 non-cache tables and all 1,422 original artifacts. Integrity/foreign keys, fixed-clock calculation parity and cross-page browser smoke checks reportedly passed. The cutover evidence `gate-4-cutover.md` is currently retained locally in the FTP-01 worktree, not yet committed to GitHub.

**Recovery:** Private verified pre-cutover schema-10 data backup at `/home/kkrug/rideworks-backups/ftp01/20261017T015331Z/data/`, paired with old code `92667ad`. Retain the backup and FTP-01 worktree pending deliberate later housekeeping.

**Separate environment:** The Owner also operates a distinct production server. Updating that server and transferring a consistent copy of the accepted development database and necessary original artifacts, while preserving server-specific configuration, is **not part of this completed Gate 4 deployment** and requires a separate Owner-directed rollout. Do not treat this completion as evidence that the other server was updated. Do not automatically start another task.


### OPS-03 — Initial accepted-data rollout to separate home-LAN production server

**Status:** **done — production rollout complete and Owner-accepted on 2026-10-28.** The Owner explicitly directed that OPS-03 be closed without further deployment, verification or Analyst review, superseding the earlier administrative closeout requirements for this task only. [JIT](docs/tasks/OPS-03.md); [issue #44](https://github.com/k14krug/rideworks/issues/44).

**Purpose:** Transfer the accepted RideWorks development release and a consistent snapshot of its cycling history, FTP timeline and original activity files to the existing private home-LAN production server, without treating dev and prod as the same machine.

**Historical execution requirements:** The JIT specified **`/TASK only`**, a Gate 1 target-specific Owner approval and a Gate 2 cutover followed by Owner final acceptance. Its original acceptance criteria covered the accepted release, coherent schema-11 history/FTP and referenced original artifacts, verified recovery backups, preserved server-specific configuration and development environment, and Owner acceptance. These remain historical criteria, not instructions to repeat the rollout.

**Historical evidence gaps:** Detailed Gate 1/2 approvals, actual deployed commit and data treatment, backup/recovery checks and smoke/verification results are not documented in the reviewed repository and issue records; independent Analyst acceptance of OPS-03 is not recorded. Owner-directed closure does not assert that undocumented checks were performed or passed. No further evidence collection, verification, Analyst review or closeout task is requested. Do not access production, resume either gate or automatically start another task.

### FTP-02 — Manual FTP entry after latest recorded date

**Status:** **done — Owner-approved and independently Analyst-accepted 2026-10-27; merged [PR #48](https://github.com/k14krug/rideworks/pull/48) at `613b0dccc6cc653ac3500b26ce9f292ac5e86037`.** [Issue #47](https://github.com/k14krug/rideworks/issues/47); [FTP-02 JIT](docs/tasks/FTP-02.md).

**Purpose:** Allow any previously unrecorded manual date-effective FTP setting, notably after the current last setting, without a qualifying ride. New settings may lower or raise FTP and take effect on their date, with the last effective indefinitely. Retain FTP-01 historical comparison, same-date and stale-write protection, existing dates/values, and training-state/plan recalculation.

**Non-goals:** No general edit/delete, automatic FTP estimates, schema migration, live data mutation, or production-server rollout. OPS-03 is separate.

**Acceptance:** Dex reported 24 focused/497 full tests on PR branch, 30 focused/532 full tests on dev integration and 17 Chromium checks on each disposable Store. Analyst reviewed source and evidence and explicitly accepted the feature; tests were not rerun by Analyst. This acceptance does not authorize production data replacement, a change to the exact target, or bypassing OPS-03 gates.


### HOME-UI-02 — Home Training State and 20-minute Performance trend cards

**Status:** **done — Analyst technical review accepted and Owner explicitly directed closure on 2026-10-28; [PR #50](https://github.com/k14krug/rideworks/pull/50).** [JIT](docs/tasks/HOME-UI-02.md); [implementation and evidence](reports/HOME-UI-02/implementation.md). Follow-up to completed HOME-UI-01; not a reopening of it.

**Purpose:** Update the Home Training State card to show the actual six-month Fitness (42-day) history with dynamic Y-axis and endpoint value (no Fitness/Fatigue/Form tiles); update the adjacent 20-minute Performance card to show the actual 12-month rolling 42-day best eligible 20-minute power (not the latest eligible ride), using the Owner's private Home mockup as visual guidance.

**Scope and acceptance:** Training State appears above Performance beside Recent Activities at desktop, with responsive mobile layouts; accepted data semantics, other Home sections and full pages are preserved. Dex reported 509 passing Python tests, 543 Chromium assertions and six fixed-clock preservation comparisons. Analyst independently reviewed source, tests, reports and synthetic screenshots and recorded **technical acceptance** on PR #50 (review ID 5691249344); Analyst did not rerun tests. The Owner subsequently instructed that HOME-UI-02 be closed, satisfying the final Owner gate; this is an explicit closure decision, **not a claim that a real-rider running-UI visual check was independently observed or verified**. No new algorithms, production changes, or private data/screenshots in Git. No further HOME-UI-02 review requested.

---

### HOME-UI-03 — Home Mileage by Year card

**Status:** in_progress — Owner's 2026-10-29 refinements implemented and verified on `task/home-ui-03-mileage-by-year`; [PR #51](https://github.com/k14krug/rideworks/pull/51) ready for Analyst review. [Results](reports/HOME-UI-03/implementation.md).

**Purpose:** Replace the compact Annual Mileage Goal Home card with an equally short Mileage by Year view comparing cumulative cycling mileage for the current and preceding two calendar years, retaining YTD, miles remaining and the rounded-up whole-mile needed/week goal arithmetic.

**Owner-approved direction:** Three cumulative lines in a calendar-clamped five-month window, blue/amber/teal series and recorded yearly totals in the legend; current-year emphasis and actual endpoint; no goal line/bar or old annual-target text; chart card no taller than Mileage Progress. Existing P3-01 distance eligibility, local calendar, annual target Settings, and needed-weekly semantics remain authoritative. The approved private mockup is shared directly with Dex, not committed; numbers are illustrative.

**Latest Owner refinement (2026-10-29):** Remove the duplicate prominent YTD headline, place remaining-goal and needed-weekly text below the chart, match the neighboring desktop Mileage Progress card height without enlarging it, use the lowest visible starting mileage as the Y-axis floor, and remove the visible coverage paragraph. Coverage remains in accessible chart descriptions and existing diagnostics. This directly supersedes the prior card presentation; JIT execution/review controls are unchanged.

**Acceptance:** [HOME-UI-03 JIT](docs/tasks/HOME-UI-03.md), including focused tests, compact responsive layout, source-aware missing states, HARD — Analyst technical review and HARD — Owner running-UI visual approval.

**Allowed invocation:** /TASK or /AUTOTASK.

**Dependency:** Accepted/merged HOME-UI-02 (PR #50); completed P3-01/HOME-UI-01. No production deployment authorized.
