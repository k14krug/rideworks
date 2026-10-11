# RideWorks — Product Requirements

**Status:** Approved controlling product requirements  
**Purpose:** Define what the application is intended to become, what the first delivery phases must accomplish, and what implementation/design tasks must trace back to.  
**Scope:** Personal, single-rider cycling training, ride analysis, performance history, training-state assessment, and later adaptive planning.

---

## 1. Product purpose

The application should stand on its own as the rider's primary place for reviewing cycling activity, understanding long-term performance, checking progress toward goals, assessing current training state, and eventually deciding what training should come next.

Strava is an important source and ecosystem, but it is not the product specification. The application may use Strava data where useful, but it must own a durable training history assembled from the best available sources and remain useful even if Strava access changes or disappears.

The core product questions are:

1. **How did I perform today?**
2. **How does today's performance compare with my previous performance?**
3. **How am I progressing toward my goals?**
4. **How is my 20-minute power changing?**
5. **Did today's workout accomplish its intended purpose?**
6. **Was today's session materially harder or easier than intended?**
7. **What is tomorrow's workout?**
8. **Eventually: given my recent training and current state, what should I do next?**

The application is not merely an activity archive. Its value comes from turning durable training history into useful, explainable review, comparison, progress tracking, and planning.

---

## 2. Product principles

These principles are controlling requirements unless explicitly superseded later.

### PR-001 — Personal application first

The application is designed for one rider. Decisions should optimize for usefulness, accuracy, explainability, and simplicity for that rider rather than hypothetical multi-user scale or commercial generality.

### PR-002 — Product-first implementation

Implementation work must support a user-visible product capability or a clearly necessary foundation for one. The data model, importer, parser, or storage layer must not become the product roadmap by accident.

### PR-003 — Durable application-owned history

The application must maintain its own durable cycling and training history from the best available combination of:

- FIT files;
- TCX and GPX files;
- Strava bulk-export data;
- Strava API data where useful;
- direct/local source files where practical;
- manual corrections and selected manual information;
- application-calculated metrics and interpretations.

### PR-004 — Source evidence and interpretation remain distinct

Original evidence, normalized source evidence, calculated metrics, estimates, and interpretations must remain distinguishable.

### PR-005 — Preserve originals

Original source artifacts should be preserved unchanged whenever available. Derived files or recalculated results must not overwrite original evidence.

### PR-006 — Provenance matters

Where materially useful, the application must be able to determine where a value came from and whether it was:

- measured;
- supplied/known;
- calculated;
- estimated;
- inferred;
- missing;
- unknown;
- not applicable.

Field presence alone must not be treated as proof that a value was measured.

### PR-007 — Historical athlete state

FTP, weight, zones, bike identity/configuration, calibration state, and similar athlete or equipment information must be treated as historical information. Today's state must not silently be applied to old activities.

### PR-008 — Reproducible and replaceable analysis

Important calculations and interpretations should be reproducible from preserved evidence. Material algorithms should be replaceable or recalculable as better methods are developed.

### PR-009 — Competing evidence may coexist

The application must not force one universal canonical value where multiple legitimate evidence channels disagree. Analysis should select evidence appropriate to its purpose and should be explainable when that choice matters.

### PR-010 — Explain results, do not hide them behind mystery scores

When the application says something such as "this session was substantially harder than intended," it should be able to show the evidence behind that conclusion.

### PR-011 — No required subjective tracking

Routine subjective inputs such as RPE, sleep, soreness, fatigue, and motivation are **not** required product inputs. Manual notes may remain possible, but the core system must work without rider questionnaires or regular subjective check-ins.

### PR-012 — Missing data remains visible

The application must not manufacture precision to fill historical gaps. Missing, estimated, inferred, calculated, and measured information must not silently become equivalent.

### PR-013 — Approved mockups guide the visual product

The approved RideWorks mockups are repository-controlled visual references:

- Activity Review: `docs/mockups/activity-review.png`
- Dashboard: `docs/mockups/dashboard.png`
- authority/version notes and image hashes: `docs/mockups/README.md`

Implementations should preserve their overall page structure, information hierarchy, density, card/panel organization, and visual character unless a concrete usability, data-availability, or technical reason justifies divergence.

The product should grow into these mockups over successive phases rather than repeatedly redesigning the interface. Features whose underlying capability does not yet exist should be omitted rather than displayed as fake placeholders.

The images predate the final product name. Any older title or wordmark visible in them is superseded by **RideWorks**.

This requirement does not freeze every color, spacing value, label, or component detail. It does establish the mockups as the intended screen direction.

### PR-014 — RideWorks identity and branded iconography

**RideWorks** is the product name. User-facing application titles, navigation chrome, product labels, and new current-state documentation must use RideWorks consistently.

Historical research reports and completed task artifacts may retain earlier working names; they are historical evidence and need not be cosmetically rewritten.

RideWorks requires branded application iconography/mark assets appropriate to the application shell and normal desktop/web presentation. Exact artwork is a visual-design decision, not a P1-01 prerequisite. The branded icon/mark must receive Owner visual approval before final Phase 1 UI acceptance.

---

## 3. Major product areas

The application is expected to develop around four primary user-facing areas. These are product capability areas, not yet a final navigation specification.

### 3.1 Dashboard

The dashboard is the intended primary operating view of the application.

It should eventually provide a concise view of:

- current performance/training state;
- progress toward important goals;
- recent activities;
- notable recent performance changes;
- selected longitudinal trends;
- the next planned workout;
- useful alerts or interpretations;
- shortcuts into deeper activity, performance, and planning views.

The approved Dashboard mockup at `docs/mockups/dashboard.png` is the preferred visual/layout reference for this screen. The real RideWorks dashboard should retain its overall hierarchy: persistent left navigation; top status/progress cards; recent activities as the primary body; next-workout and insight panels to the right; and trend/progress panels below. The complete mockup is a destination, not a requirement that every element exist immediately. Missing capabilities should be omitted until real rather than replaced with fake content.

### 3.2 Activity review

Activity review answers: **What happened during this ride, and what does it mean in context?**

The approved Activity Review mockup at `docs/mockups/activity-review.png` is the preferred visual/layout reference. The implemented RideWorks screen should preserve its overall hierarchy as capabilities arrive: persistent left navigation; strong activity identity/header; a top row of important ride metrics; a large central ride chart; supporting analysis panels below; and a right-hand ride-summary/insight column. The interface may be thinner in early phases, but it should grow into this structure rather than being replaced by a different generic application layout.

It must eventually support:

- ride summary;
- power, heart-rate, cadence, speed/elevation and other available streams;
- important/best efforts;
- power-duration results;
- workout structure or intervals where known or detected;
- comparison with intended workout purpose where known;
- comparison with recent and historical performance;
- notable findings and explainable interpretations;
- visibility into source/provenance when something looks wrong.

### 3.3 Performance history

Performance history answers: **Am I improving, declining, or changing?**

The first emphasized longitudinal metric is **20-minute power**.

The product should eventually support:

- 20-minute power over time;
- FTP history;
- arbitrary-duration power history where detailed source data permits;
- power-duration curves;
- monthly/yearly bests;
- comparisons between periods;
- watts/kg where historical weight is known;
- relationships between training patterns and later performance.

**Owner-directed Power Curve follow-up (2026-10-11):** Add a multi-duration power curve to the existing Performance view with two independently selectable historical comparisons, and a curve in Activity Review comparing the selected ride **by default to its own previous six weeks** (not the six weeks prior to viewing the page). The selected ride and later rides are excluded from that historical baseline. Use eligible source-observed windows with honest source/coverage limitations; preserve accepted 20-minute Performance results. See [PC-01 design](design/PC-01-power-duration-curves.md) and [acceptance criteria](POWER_CURVE_ACCEPTANCE.md). This follow-up does not reactivate deferred Phase 6.

### 3.4 Training plan

Training planning answers: **What am I supposed to do next?**

**Phase 5 owner-directed initial behavior (2026-10-10):** show **today's recommended ride** prominently on Home, and a dedicated **Plan** rotation from today **through the next three upcoming recommended hard-session days**, including the intervening low-intensity days. Use an explainable rolling recommendation, not fixed workout weekdays. **Never recommend a no-ride/rest day**; the rider may independently skip and a past no-record day may be treated as *assumed rest for planning* only when synchronization supports the inference. Distinguish recommendations from rider-confirmed intent and actual completed activity. See [P5-01 design](design/P5-01-rolling-training-plan.md).

Later it should become adaptive: actual workout results, recent performance, recovery/training state, goals, schedule constraints, and changing conditions should be able to alter future recommendations.

Training-state assessment and training planning must remain conceptually distinct:

- training state: **Where am I now?**
- planning: **What should I do next?**

---

## 4. Functional requirements

### Activity and source requirements

**ACT-001 — Application-owned activity identity**  
An activity must have durable application-owned identity independent of Strava or any individual source file.

**ACT-002 — Multiple sources per activity**  
Multiple sources may describe or enrich one activity. A FIT file, Strava export row, Strava API record, manual correction, or later source must not automatically become separate activities.

**ACT-003 — Conservative source association**  
Source matching must prefer explicit identity or strong multi-factor evidence. Ambiguous associations should remain unresolved rather than being silently forced.

**ACT-004 — Preserve original artifacts**  
When an original FIT/TCX/GPX or equivalent artifact exists, preserve it unchanged.

**ACT-005 — Typed normalized source evidence**  
The application may persist typed normalized extraction of source evidence for efficient application use, while retaining the original artifact as durable evidence.

**ACT-006 — Preserve native timing**  
Import must not silently interpolate, resample, smooth, remove gaps, manufacture aligned samples, or discard duplicate timestamps merely to produce cleaner streams.

**ACT-007 — Source summaries and calculated summaries coexist**  
A source-supplied average or summary must not be overwritten by an independently calculated value.

**ACT-008 — Later enrichment**  
A later source must be able to enrich an existing activity, for example by adding detailed streams to a historical summary-only activity.

**ACT-009 — Manual correction**  
The user must eventually be able to correct classifications, activity/source associations, athlete state, and other incorrect inferred or automated information without destroying original evidence.

---

### Activity review requirements

**REV-001 — Useful single-ride summary**  
For a supported activity, the review view must show the key available ride facts needed to understand what happened.

**REV-002 — Time-series review**  
Where available, the activity view must support review of power and heart rate over time. Other streams may be added according to usefulness.

**REV-003 — Best-effort analysis**  
The application must calculate and present best efforts from detailed power data, including at minimum a 20-minute result when the activity duration and data permit it.

**REV-004 — Historical context**  
The activity view must be able to place today's result against prior performance rather than presenting it in isolation.

**REV-005 — Optional future ride-to-ride comparison**  
Manual pairwise comparison between two selected rides is not a required Phase 2 capability. It remains a possible later interaction if a concrete use case proves valuable, such as comparing repeated executions of the same workout, race, or route. Historical performance context is controlled by REV-004 and the PERF requirements.

**REV-006 — Workout intent**  
When a ride has a known planned purpose or workout target, the application must retain that intent separately from the completed activity evidence.

**REV-007 — Workout outcome**  
The application must eventually determine whether the completed ride appears to have met the intended workout purpose using transparent rules and available evidence.

**REV-008 — Intended-versus-actual interpretation**  
The application should surface useful statements such as:

- session substantially harder than intended;
- session substantially easier than intended;
- planned work completed;
- final intervals materially faded;
- unusually strong sustained performance;

provided the supporting evidence can be shown.

**REV-009 — Explainability**  
Interpretations must be traceable to concrete evidence: what was expected, what occurred, how they differed, and what calculation or comparison was used.

**REV-010 — Inspectability**  
The normal activity page should remain clean, but the user must eventually be able to inspect source values, calculated values, missing data, streams, and source associations when a result appears questionable.

---

### Performance-history requirements

**PERF-001 — 20-minute power history**  
The application must maintain and present 20-minute power history from eligible activities with sufficient power evidence.

**PERF-002 — Current versus recent/historical context**  
Today's 20-minute result should be comparable against useful prior periods such as recent weeks, year-to-date, prior year, or lifetime where appropriate.

**PERF-003 — Arbitrary-duration future capability**  
The design must not hard-code the product around only a fixed list of durations. Detailed power data should eventually support arbitrary-duration analysis.

**PERF-004 — Eligibility and evidence quality**  
Measured, estimated, and other power evidence may require different eligibility rules for personal records and longitudinal comparisons. Low-confidence estimates must not silently pollute lifetime bests.

**PERF-005 — Historical athlete context**  
Where metrics depend on FTP, weight, zones, or other athlete state, use the state appropriate to the activity date whenever possible.

---

### Goal requirements

**GOAL-001 — Goal progress is a first-class dashboard concern**  
The application must be able to show progress toward rider goals, not merely activity totals.

**GOAL-002 — Goals are broader than mileage**  
The product must not assume annual mileage is the only type of goal. Future goal types may include performance, consistency, event preparation, workout completion, or other useful targets.

**GOAL-003 — Do not overbuild a generic goal engine initially**  
The first release may support a narrow set of useful goals. A universal configurable goal framework is not required before the product proves value.

---

### Dashboard requirements

**DASH-001 — Dashboard as primary overview**  
The dashboard should become the main place to answer: How am I doing now, what changed recently, how are my goals progressing, and what comes next?

**DASH-002 — Recent activities**  
The dashboard must eventually provide recent activities with enough information to identify important rides and open detailed review.

**DASH-003 — Performance snapshot**  
The dashboard should surface selected current performance/trend information, including 20-minute power when useful.

**DASH-004 — Goal progress**  
The dashboard should show progress toward selected goals.

**DASH-005 — Next workout**  
The dashboard should show the next planned workout when planning data exists.

**DASH-006 — Useful insights only**  
Dashboard insights must be actionable or informative and explainable. Avoid filling the screen with generic observations merely because they can be calculated.

---

### Training-state requirements

**STATE-001 — Training state is distinct from planning**  
Training-state analysis answers **Where am I now?** Planning answers **What should I do next?** A current-state calculation must not silently become a workout prescription.

**STATE-002 — Workload inputs retain evidence class and athlete context**  
Training-load calculations must retain the evidence they used and any athlete-state inputs they depend on. Where load is normalized to FTP, heart-rate thresholds, weight, zones, or similar values, use date-appropriate historical state rather than applying today's value backward.

**STATE-003 — Missing and lower-confidence load evidence stays visible**  
An Activity without eligible evidence for a chosen load method must not silently contribute zero load. Power-derived, heart-rate-derived, external-load, estimated-power, and missing load evidence must remain distinguishable.

**STATE-004 — Training state must be explainable and reproducible**  
Important load/state calculations must be versioned or otherwise reproducible from retained Activity evidence and athlete context. If RideWorks says fatigue/load is elevated, the rider must be able to see the underlying recent work and model assumptions.

**STATE-005 — No opaque fitness/readiness score as the foundation**  
RideWorks must not begin with one unexplained score that claims to represent fitness, fatigue, readiness, or form. Composite summaries are allowed later only when their inputs and interpretation remain inspectable.

**STATE-006 — Objective core; subjective data may enrich later**  
The first useful training-state model must work from retained objective training history without requiring daily questionnaires. Optional RPE, fatigue, sleep, soreness, motivation, illness, or notes may enrich later interpretation.

**STATE-007 — Performance and training load are related but not interchangeable**  
Recent workload, long-term workload, recovery spacing, hard-session frequency, and performance changes may inform current-state interpretation, but a load score must not be presented as measured performance or physiological truth.

---

### Planning requirements

**PLAN-001 — Planned workout representation**  
The application must eventually represent a planned workout independently from the completed activity that may fulfill it.

**PLAN-002 — Today's intent**  
The application should be able to tell what today's workout was intended to accomplish when a workout is planned.

**PLAN-003 — Upcoming rolling rotation**  
The application should show today's recommended ride and the daily rotation **through the third next upcoming hard-day recommendation**, including all intervening days, with tomorrow naturally included. The user does not have fixed workout weekdays. No Rest/no-ride recommendation is permitted; skip days are assumed rest only as qualified past actual-history context, not as scheduled workouts.

**PLAN-004 — Actual outcome can affect later planning**  
Later adaptive planning must be capable of changing future workouts based on what actually happened rather than blindly following a static schedule.

**PLAN-005 — Planning recommendations are explainable**  
If a future workout is changed or recommended, the application should be able to state the evidence and reasoning.

---

## 5. Data and analysis requirements that support the product

These requirements are supporting constraints, not user-facing phases by themselves.

**DATA-001 — No provenance-free universal activity summary**  
Do not turn the Activity object into a universal collection of canonical distance, elevation, power, heart rate, calories, and similar values when legitimate source disagreement may exist.

**DATA-002 — Source-centered evidence ownership**  
Imported evidence belongs to the source that supplied it. FIT summaries belong to the FIT source; Strava values belong to the Strava source; streams belong to the supplying source.

**DATA-003 — Material derivations retain context**  
Important derived results should retain or be able to reproduce their inputs, method/version, assumptions, and relevant uncertainty.

**DATA-004 — Analytical persistence by usefulness**  
Persist derived analytical metrics when they are useful as durable/versioned analytical history or repeatedly consumed longitudinally. Cheap presentation-only aggregates may be calculated on demand.

**DATA-005 — No universal source ranking**  
Source/evidence selection depends on analytical purpose. The application should not encode one global ranking that assumes one source is always best.

**DATA-006 — Reparse/recalculate capability**  
Preserved originals must allow normalized extraction and derived analytical results to be rebuilt when parsers or algorithms materially improve.

---

## 6. Explicitly deferred areas

The following are important but are **not prerequisites for the first useful application slice**.

- exact database product and schema;
- final web/framework choices;
- final navigation and complete UI design;
- exact training-load model;
- exact recovery/fatigue model;
- adaptive planning algorithm;
- final goal framework;
- exact AI/LLM runtime role;
- automatic local-file watching;
- complete Strava synchronization mechanism;
- outdoor estimated-power reconstruction implementation;
- final outdoor estimated-power confidence/eligibility rules;
- final use of weather/elevation services;
- generalized multi-user/commercial architecture.

Deferred does not mean rejected. It means these areas should not block proving the core product experience.

---

## 7. Delivery phases

The phases below are the initial product delivery sequence. They should be changed only when there is a clear product reason, not because a lower-level implementation task happens to be convenient.

### Phase 1 — Useful single-ride review

**Goal:** Import a real representative ride and produce an activity-review experience useful enough to open after a ride.

Minimum user-visible outcomes:

- activity exists with durable application identity;
- original source artifact is preserved;
- key summary evidence is available;
- native power and HR streams are reviewable when present;
- best 20-minute power is calculated when possible;
- today's ride can be understood without opening Strava;
- source/calculated distinctions remain inspectable behind the normal view.

Phase 1 is **not complete** merely because import/storage works.

### Phase 2 — Historical context and performance history

**Goal:** Stop treating a ride as an isolated event and make the rider's existing history practically usable.

Minimum user-visible outcomes:

- the complete known Strava-export activity population is imported into RideWorks durable history, including file-backed and CSV-only activities without manufacturing missing evidence;
- the Activities browser remains usable across the resulting ~1,400-activity history through pagination plus practical search/filter/sort;
- actual source activity titles are preserved and preferred with provenance when available, while type/subtype remain separate;
- 20-minute power history is available across a conservative trusted cohort;
- for the initial trusted trend, eligible Virtual Ride native source-power streams may contribute when they satisfy the accepted complete-window rules; outdoor power values are excluded from this trusted performance trend in Phase 2 because their provenance/quality is considered suspect;
- today's eligible 20-minute result is shown against the **prior six-week best**, excluding the current activity, using neutral presentation rather than assuming higher/lower is inherently good/bad;
- multiple-source/activity enrichment works in real history, including enrichment of an already-known Activity rather than creating a duplicate when the relationship is established;
- missing, ineligible, ambiguous, or lower-quality evidence is handled visibly rather than silently substituted;
- a normal forward-looking Strava synchronization path can bring in/enrich new activities after the historical export baseline without bulk-harvesting old API history.

### Phase 3 — Useful dashboard

**Goal:** Make the application useful before opening an individual activity.

Minimum user-visible outcomes:

- recent activities;
- selected current performance/trend information;
- 20-minute power trend or snapshot;
- at least one meaningful goal-progress element;
- next workout area when plan data exists;
- selected useful insights based on already-trusted analysis.

The supplied dashboard mockup is the long-term direction. Phase 3 requires a useful subset, not feature parity with the mockup.

### Phase 4 — Training state

**Goal:** Answer "Where am I now?" using transparent longitudinal evidence from completed training history.

Candidate inputs may include:

- recent workload;
- longer-term workload;
- training intensity;
- hard-session frequency;
- recovery spacing;
- recent performance changes;
- recent races or unusually demanding sessions;
- optional subjective information later when useful.

The first Phase 4 model must **not depend on planned-workout or adherence data**, because planning now follows in Phase 5. Phase 5 may later enrich training-state interpretation with planned-versus-actual outcomes without redefining the underlying state history.

The exact load/state model remains open and must be evaluated rather than copied blindly from industry convention. Classic TSS/CTL/ATL/TSB-style methods are an important reference baseline, not an automatic product decision.

Minimum user-visible outcomes by Phase 4 completion should include:

- inspectable per-activity or per-day training-load evidence for the selected method;
- recent-versus-longer-term workload context;
- an explainable current-state presentation rather than one mystery score;
- visible missing/ineligible evidence and athlete-context assumptions;
- at least one longitudinal view that can be compared with already-trusted Performance history.

### Phase 5 — Workout intent, outcome, and initial planning

**Goal:** Connect what was planned with what actually happened and show what comes next.

Minimum user-visible outcomes:

- planned workout/intended purpose represented separately from completed activity;
- ride review indicates whether key workout goals were achieved;
- explainable intended-versus-actual findings such as "harder than intended" are supported;
- Home shows today's recommended ride; the Plan page shows the full daily rotation from today through the **next three recommended hard-session days**, not a fixed time window. All recommended days have a ride option; past skipped days may count as assumed rest when synced;
- Phase 4 training state may inform presentation and later planning decisions, but planning remains conceptually separate.

### Phase 6 — Adaptive planning

**Goal:** Answer "What should I do next?" and adapt future training based on actual training outcomes and current state.

The system should eventually be able to alter future workouts when prior training materially changes the situation and explain why.

---

## 8. Requirements traceability for tasks

Every implementation/design task should reference one or more requirement IDs or a phase outcome.

Examples:

- `REV-003`: calculate best 20-minute power from a native power stream.
- `ACT-004`, `DATA-006`: preserve original FIT and support reparsing.
- `PERF-001`, Phase 2: persist/query 20-minute history across eligible activities.
- `REV-006`, `PLAN-001`: represent planned workout intent separately from completed ride evidence.

A task that cannot identify what requirement or phase outcome it supports should be questioned before implementation.

Technical tasks are allowed when necessary, but their task brief should state the user-facing capability they enable.

---

## 9. Product decisions already settled outside this document

This requirements document does not replace detailed design decisions. It controls **what** the application must accomplish; design decisions define **how** supporting concepts behave.

The following project decisions remain in force:

- DESIGN-001 — Durable Activity and Provenance Model;
- DESIGN-002 — Source-Centered Storage and Import Representation.

Their core implications include:

- application-owned Activity identity;
- multiple Sources per Activity;
- preservation of original artifacts;
- typed source-centered normalized evidence;
- historical state as analysis context;
- reproducible derived interpretations;
- conservative activity reconciliation;
- native timing preservation;
- source summaries and calculated summaries coexisting;
- no universal canonical-value table initially.

These design decisions support this requirements document. They are not substitutes for product requirements and must not independently drive the roadmap.

---

## 10. Special topic: outdoor estimated power

Outdoor estimated-power reconstruction remains an important design exploration but is not an immediate implementation target.

Strong principles already established include:

- original files remain unchanged;
- reconstructed watts are explicitly estimated, not measured;
- physics alone is insufficient;
- HR can constrain an estimate but is not a wattmeter;
- historical FTP/weight/bike state matters;
- uncertainty/confidence must be explicit;
- estimated power may be suitable for some analyses and unsuitable for others depending on confidence and time scale.

This feature should re-enter implementation when the core activity/performance product has enough structure to make its downstream use and eligibility rules clear.

---

## 11. Non-goals for the near term

The near-term project is **not** trying to:

- recreate Strava's social network;
- build a commercial multi-athlete platform;
- support every possible cycling device/workflow immediately;
- produce one opaque "fitness score" that substitutes for evidence;
- require daily wellness questionnaires;
- solve adaptive training planning before ride review and performance history are useful;
- build a bulk historical Strava API harvester;
- force incomplete historical activities to look more complete than they are.

---

## 12. Definition of product progress

Project progress should primarily be measured by useful rider capabilities, not by infrastructure volume.

A phase is successful when the application can answer a new real question reliably enough to be useful.

Examples:

- **Phase 1:** "How did this ride go?"
- **Phase 2:** "How does this compare with my past performance?"
- **Phase 3:** "How am I doing overall right now?"
- **Phase 4:** "What is my current training state?"
- **Phase 5:** "Did I accomplish today's workout, and what is tomorrow?"
- **Phase 6:** "What should change next because of what actually happened?"

That sequence is the guardrail against returning to an infrastructure-first project.

---

## 13. Current open product questions

These remain deliberately open and should be answered when their phase approaches:

1. Which additional activity-review metrics, beyond the approved Phase 1 minimum, are valuable enough to add in later phases?
2. Which goal types should be implemented first?
3. What exact evidence should trigger statements such as "harder than intended"?
4. What training-state model best fits this rider and remains explainable?
5. What historical athlete-state evidence (especially FTP) is available or must be entered manually for load normalization?
6. When should estimated outdoor power become eligible for training-load use, and at what confidence level?
7. What planning source or representation should supply tomorrow's workout initially in Phase 5?
8. What parts of planning should remain deterministic versus AI-assisted, if AI is used at all?

These questions should not be answered prematurely merely to complete a schema or architecture diagram.

---

## 14. Working product statement

> Build **RideWorks** as a durable personal cycling-training application that explains how today's ride went, shows how performance is changing over time, tracks progress toward goals, connects completed work with planned work, and eventually uses trustworthy historical evidence to decide what training should come next.

RideWorks owns the history. Sources provide evidence. Analysis explains what happened. Performance history shows what is changing. Planning determines what comes next.