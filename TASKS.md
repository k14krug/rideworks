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

Phase 1, Phase 2, STRAVA-004 and Phase 3 are accepted and complete. P4-02 is the current implementation task.

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

**Status:** active — P4-01 research/design accepted; P4-02 implementation and review follow-up ready for Analyst review.

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

**Status:** in_progress — 2026-10-10 direction updated to **Elevate-first estimated power-stress selection** and **taller interactive chart**. HARD — Analyst method/implementation review pending; Owner Gate 2 did not accept the previous version. No merge or task/phase acceptance.

**Purpose:** Produce a useful, repeatable Fitness/Fatigue/Form view for this recreational rider, grounded in qualified measured-power stress, a practical approximate HR-based fallback, the approved dated FTP history, and explicit source quality.

**Owner-confirmed design context:** [P4-02 training-state direction](docs/design/P4-02-training-state-direction.md), read together with accepted [DESIGN-003](docs/design/DESIGN-003-training-state-model.md) and the [Phase 4 acceptance contract](docs/PHASE_4_ACCEPTANCE.md). The October 9 follow-on conversation supports HRSS-style outdoor fallback and a 42-/7-day interactive longitudinal chart. The Owner subsequently approved the **pragmatic Elevate-style unscored-ride numerical contribution of zero** (retain original missing-stress evidence), **prior-day Form**, a **zero initial seed**, and **no v1 projections/fixed training zones**. The Owner approved using **58 bpm resting / approximately 158 bpm max** and modeled **143 bpm threshold** as **explicit retrospective assumptions** for older rides without dated HR evidence, plus prioritizing adequately covering HR stress over materially partial power. The JIT specifies a simple versioned fixed-coefficient HRSS recipe; these inputs are assumptions, not historical measurements. This is **not** an implementation authorization.

**Next gate:** The [§13 distribution-screen diagnosis](reports/P4-02/distribution-screen-followup.md) is accepted as a bounded practical training-model guardrail. [JIT §14](docs/tasks/P4-02.md) **authorizes implementing** a versioned Elevate-style estimated whole-session power score from trusted recorded watts, traceable moving duration and dated FTP, with ≥80% total observed timeline / ≥50% every 300 seconds / ≥600 seconds contiguous observations, documented exclusions and uncertainty. This must supersede automatic HR preference when eligible session-power estimate exists. **Mandatory Oct 7 regression must select and display independently derived power stress** instead of the previous 38.45 HR stress; September 16 HR remains covered. Dex implements/tests/reports changed sources, model series, cache/versioning, browser and preserved originals, then returns to HARD — Analyst implementation Gate 1. Owner Gate 2 remains unaccepted. Keep PR #24 draft, no merge or Phase 4 acceptance.

**Dependency:** P4-01 accepted; P4-02 design/JIT finalized and explicit implementation invocation received. Analyst and final Owner review outstanding.

### Phase 5 — Workout intent, outcome, and initial planning

Planning now follows Training State. It is not started.

### Phase 6 — Adaptive planning

Unchanged; not started.
