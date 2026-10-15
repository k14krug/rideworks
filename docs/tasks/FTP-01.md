# FTP-01 — Database-owned FTP history and editable 20-minute comparison

**Status:** Gate 0 independent Astra review completed 2026-10-14; Analyst accepts its findings and authorizes **Gate 1 implementation only**, subject to the controls below. This revision supersedes the pre-review version of FTP-01.
**Issue:** [#37](https://github.com/k14krug/rideworks/issues/37).
**Gate 0 evidence:** [Astra review](../../reports/FTP-01/astra-gate-0-review.md), [review PR #38](https://github.com/k14krug/rideworks/pull/38).
**Objective:** Make SQLite the authoritative source of editable historical FTP, migrate the 66 known Strava settings without losing their original evidence, and integrate the interactive FTP/20-minute-power comparison and manual editing into RideWorks. At final rollout, **all three FTP CSV files are removed from the active repository/application/deployment; there is no archival FTP CSV**.

## 1. Requirements Used and current evidence

- Owner's October 14 decisions: FTP history belongs in the production database; no retained FTP CSV archive; all orange **and** gray performance dots may be selected; the selected ride supplies an editable suggested FTP and effective date; the Owner may raise or lower FTP as judged appropriate; this is a manual decision, not an automated correction system.
- [AGENTS.md](../../AGENTS.md), [product requirements](../PRODUCT_REQUIREMENTS.md), [Phase 4 acceptance](../PHASE_4_ACCEPTANCE.md), historical FTP semantics formerly described in data/athlete/README.md, accepted Performance evidence rules, and the currently deployed application patterns.
- Astra's review of the code and read-only local metadata at commit a85ff5a. Gate 0 was a plan review, **not** an implementation rehearsal or production test. Its reported local counts are observations, not hard-coded application invariants.
- Existing source locations: data/athlete/strava_ftp_history.csv and rideworks/data/strava_ftp_history.csv (the two matching 66-entry sources), plus legacy root ftp-history.csv (52 unrelated older entries). The last is **not** migration input.
- The local 2026-10-13 HTML graph is reference UX/evidence only: the eligible graph cohort must be recomputed from current RideWorks data, never read from this frozen HTML/report or its private builder.

## 2. Execution Control

**Allowed Invocation:** /TASK only. A fresh /TASK FTP-01 may start **Gate 1** once this revised Analyst-authored JIT is committed on refreshed main. No /AUTOTASK or automatic gate crossing.

- **Gate 0 — HARD — Analyst (Astra), COMPLETED.** Independent pre-code review accepted for planning purposes; only its verified findings, not unimplemented claims, are adopted here.
- **Gate 1 — Storage/consumer implementation; then HARD — Analyst.** Dex implements the FTP schema, safe *explicit* bootstrap, history/provenance API, all runtime consumers, cache consistency, full synthetic/copy-store verification and rollback rehearsal. Sources remain present during this gate. **No live-production bootstrap, deployed cutover, production CSV deletion or UI implementation.** Dex stops for Analyst review. Do not proceed to Gate 2 without explicit Analyst authorization.
- **Gate 2 — Editor/chart and retirement staging; then HARD — Analyst.** After Gate 1 acceptance, Dex integrates the graph/editor and verifies end-to-end behavior on disposable/consistent private-copy stores; prepares final code/install/package with all FTP CSVs retired, plus an executable guarded live promotion checklist. Deletions in the **task branch** are allowed at this gate only after import has been rehearsed and the production migration input is still safely available in the *old* running release. **Do not deploy, delete the live files, change the live database, or merge prematurely.** Stop for Analyst code/test and Owner visual review.
- **Gate 3 — HARD — Owner, live promotion authorization.** Owner reviews the running preview and explicitly authorizes a scheduled controlled production change. Owner approval must identify the current production store, consistent backup, application/source version to use for bootstrap, source removal and recovery steps. Approving the code/visuals alone is not blanket authorization to write the live DB. Dex stops before any live write until Owner expressly authorizes it.
- **Gate 4 — controlled promotion/verification; then HARD — Analyst and HARD — Owner acceptance.** With separate explicit Owner authorization, stop app/sync writers, back up, perform verified original-source bootstrap on the current live DB before switching to DB-only release, then cut over and remove the FTP CSV files from active checkout/deployed install. Validate services/cross-page behavior and restore method. On error, stop and restore matched code+database, not a partial downgrade. Obtain final reviews; no claim of done/merge/issue closure before the accepted rollout requirements are met. If Owner chooses to execute the commands locally, provide precise inspected commands and require their results before declaring success.

Dex must not edit the JIT's gates, scope or acceptance criteria; raise conflicts with the Analyst/Owner. Continue FTP-01 rather than starting unrelated tasks or Phase 6.

## 3. Gate 1: authoritative SQLite FTP history

### Storage and provenance contract

Use compact FTP-specific SQLite storage, **not** a generic athlete-state engine:

- Effective history entries have stable identities, date-effective starts and positive integer watts; derive the exclusive end from the next start (last is open). Duplicated watt values on different dates are legitimate distinct entries.
- Preserve **all 66 imported original date/value observations** as an immutable record inside SQLite even if their corresponding active entry is later edited or deleted. Record the validated import batch/source digest, source description, importer version and time. Retain a link between imported observation and original active entry identity when possible.
- Maintain an append-only **FTP-specific edit record** for each Owner add/edit/move/delete with timestamp, before and after values/effective dates, affected stable entry identity, source category (imported setting vs Owner-adjusted/manual), optional linked originating Activity/evidence method, and reason/notes if supplied. Deleting active history does **not** erase original evidence or earlier edits. Edited imported entries must not keep an unqualified label claiming their new value came from Strava.
- Track a single durable history revision/signature used for coherent reads, optimistic edit submissions, and cache invalidation. The revision change, edit record, and history mutation are one SQLite transaction. It is fine to choose a small schema suited to this one rider; explain it in implementation notes.

### Date, validation and unknown-state policy

- Effective from date **inclusive**, until next setting date **exclusive**. Use existing athlete-calendar interpretation America/Los_Angeles, independent of browser timezone. Preserve the existing uncertain-source-timezone boundary rule, including neighboring distinct entries with equal watts. Do not invent FTP before the first known entry.
- Inserting between entries splits the earlier interval. Moving an entry potentially changes *two* neighborhoods. Same-date insert/move onto an occupied date **rejects**, exposes the conflicting record and requires a separate explicit edit; no implicit replace or merge. Manual equal-watt entries at different dates are allowed.
- Deleting first makes earlier dates unknown until the next first; deleting middle extends predecessor; deleting last extends predecessor indefinitely; deleting the only/all entries leaves no FTP. No implicit replacement with today's FTP. Old rides with missing FTP may still have valid HR-based stress. An intentionally empty history remains intentionally empty across restarts.
- Owner-confirmed manual entry **before** previously known history is allowed and supplies FTP from that new date forward; it is not automatic retrospective inference. For this first historical editor, prevent adding or moving entries to a **future athlete-calendar date**; today and prior dates are allowed. No arbitrary physiological maximum for watts: require a positive integer plus safe input bounds and clear server validation.
- In the edit UI, any explicit entry can be edited/deleted with a preview and confirmation. Save is rejected if the client history revision/entry version is stale (two-tab race), with reload-and-review feedback. Failed edits must change neither history nor audit record nor cache revision.

### Schema, bootstrap and recovery semantics

- **Schema migration is not bootstrap.** New empty Stores get an empty table and a legitimate initialized-empty state, not a copy of the Owner's FTP. Existing pre-upgrade Stores are identified as *migration required* until explicitly bootstrapped; installing the schema alone is **not** success and must not masquerade as intentionally unknown FTP. If detection of an older blank Store needs nuance, document and test it instead of auto-seeding.
- While original files still exist, create an **explicit, narrowly scoped bootstrap command/operation**, taking source path and explicit target store; do not silently bootstrap in normal Store construction or on HTTP page view. Validate equality of the two sanctioned 66-entry files plus approved SHA-256 cb990c18e969d0d12f1d524bea22cf8b596746171f179f6241748394b87ad073, 66 chronological entries, proper inclusive/exclusive bounds, valid ISO dates and integer-positive watts **before starting the import**. Do not import the root 52-row legacy CSV.
- Insert original observations, active settings and durable import completion marker in **one atomic transaction**, with exact ordered date/value comparison. Schema state, bootstrap-complete and intentionally empty are distinct. A completed bootstrap replay must be a **no-op even after user edits/deletions**; never restore removed values. Missing/different source, nonempty unmarked history, conflicting import, partial/uncertain commit or invalid marker must stop and report, never merge silently.
- A new empty Store must work without historical FTP; an **existing** unbootstrapped Store must show a clear migration-required diagnostic and not quietly serve misleading empty-FTP analytics. Bootstrapping is a controlled one-time import, not a permanent hard-coded 66-row seed in source code, JSON or SQL.
- Rollback pairs compatible code **and** DB version: pre-upgrade code cannot read the new schema. Rehearse restore from a consistent pre-migration database plus its matching old release. Preserve current upgraded DB if recovery occurs after edits; restoring an older backup loses later edits unless separately recovered. Never decrement PRAGMA user_version as an improvised downgrade.

### Runtime consumers and calculation consistency

Audit/refactor every current FTP consumer to a store-scoped authoritative DB reader, including:

- training_state.ftp_history/ftp_on/ride_results, per-ride input signatures and training_stress_cache, daily_series/Training State and training_home;
- planning.completed_history, plan's separate current FTP lookup, activity_context and classify_activity, planning_classification_cache, and confirmed planning_intents source context;
- Home's Training State and Plan summaries, Activity Review/planning_page context and current-FTP display;
- legacy verification/diagnostic scripts that directly load packaged CSV history.

An entire request/analysis sees **one coherent FTP history snapshot/revision**. Do not load FTP outside a subsequent write transaction and accidentally mix revisions inside the same request; reuse/propagate one read within the actual Store transaction. A whole-history signature in per-ride cache keys is acceptable initially. Measure full-history cold refresh cost before attempting targeted optimization. The daily 42-/7-day series is recomputed per request; preserve this behavior.

**Behavior to preserve:** normalized power/duration stress scales as inverse-square FTP; current selected stress can switch between eligible power and HR fallback when FTP becomes known/unknown; HR-derived candidates are FTP-independent but the selected method might change. Actual watts, 20-minute evidence, power curves, observed work kJ, source selection and original files do not change. FTP edits may change Planning automatic classification and recommendations, but Owner classification overrides take precedence. Previously saved confirmed intents, their FTP at confirmation, feedback and rider corrections are immutable historical context: do not rewrite. New intents may use current FTP context with an honest DB-history signature/provenance field instead of a misleading CSV hash name. Existing literal wattage targets in planning.recommendation remain **unchanged** in FTP-01; rescaling targets is a separate future policy decision.

## 4. Gate 2: FTP history chart/editor

### Placement and visual evidence

Add **FTP History / FTP Comparison within Performance** with clear navigation from Performance and, where useful, Training State; preserve existing 20-minute, rolling, Power Curve and other accepted views. A new top-level nav destination is not required. Match the useful Dex standalone plot *in substance* while adopting the existing RideWorks shell and source of truth.

- Blue **step line** from active database history with actual blue markers **on exact FTP-setting dates**, each selectable for edit/delete, including date, watts, effective interval and provenance. The synthetic line endpoint through the visible current date is **not** a real setting marker.
- Source performance points from performance.performance_history(store) and its current eligible dated points, **not** raw rows, stale entries, or the frozen 879-point export. Respect Performance freshness/pending indications and existing rebuild rules; do not change eligibility, source precedence or best-20 calculation. A new Store with no FTP still supports the graph and manual add.
- Y value for each point: **unrounded 0.95 × that ride's best-20 average watts**. Orange when that exact unrounded value is strictly greater than its comparable dated FTP; gray when it is at/below (ties gray). Compare **before** rounding. Show raw best-20 in tooltip/evidence. For integer editable suggestion use nearest integer watts with 0.5 ties rounding **up**; do not use banker's rounding. The suggestion is an initial value, not a claim of physiological FTP.
- Include eligible rides with no comparable dated FTP (e.g. 150 originally outside recorded prehistory, or rides rendered uncertain by source-date timezone ambiguity) in a visually distinct **"FTP unavailable / comparison uncertain"** category; never silently show them gray/orange. Display the reason. All eligible dots including that category can be selected to suggest a manual entry.
- Orange, gray and unavailable categories are togglable. Display dynamic counts and legend; do **not** hardcode 879/69/810, 150, or 66 as permanent facts. Tooltips provide activity/date/source, best-20 watts, 95% watts, matched FTP or unavailable reason, difference when comparable, and link to Activity.
- Provide useful full-history range, zoom into a selected period, pan/date navigation, reset-to-all and at least a date-range control or slider of comparable usefulness to the standalone Plotly chart. Browser/native SVG is preferred if it satisfies selection/zoom/touch/keyboard usability without a 4.8 MiB embedded report; a locally bundled Plotly dependency is allowed only if justified by implementation/test evidence, with no CDN or frozen-data embedding. Do not claim a few presets alone recreate reference zoom/pan.

### Editing behavior

- Selecting **any** orange, gray or unavailable point freezes the selected Activity, prefilled suggested FTP and *athlete-calendar* activity date while the form is edited. Hover/repaint must not overwrite the pending edit; opening the Activity is a separate action.
- Provide an accessible all-points list/keyboard selection alternative for dense/overlapping dots. An entry can also be added manually on **any permitted date** without a ride and existing FTP settings can be selected/edited/deleted independently of the plot.
- Editable watts and date; show current FTP, candidate and effect on **the relevant affected effective-date intervals** before save. For moved/deleted entries show both old and new neighboring effects, including loss of known FTP and full-history-empty behavior. Explain that downstream Training State may change on later days, without pretending to calculate an exact new curve in the preview. Require explicit delete confirmation. Same-day collision and two-tab stale-preview errors must be clear.
- Persist with existing web request Origin/nonce/form-validation conventions. Validate server-side actions, entry/activity existence, allowed date, integer watts and expected revision; no arbitrary FTP inference or automatic Strava update. Preserve other UI filters, selected activity identity, chart zoom and focus after saves where practical; repaint orange/gray/unavailable status from latest DB after the save.

## 5. Final FTP CSV retirement and installation boundary

At the **Gate 2 task branch and final promoted release**, delete/retire:
1. data/athlete/strava_ftp_history.csv;
2. rideworks/data/strava_ftp_history.csv;
3. legacy root ftp-history.csv plus its inactive absolute-path loader load_ftp_history.py if no live RideWorks consumer exists (Astra found none).

Do **not** import that third legacy dataset or preserve another CSV/JSON/source-code copy as an archival dataset. Remove obsolete FTP CSV package-data directives, current loaders, current-use documentation and active verifier/test dependencies. Adapt current verification to SQLite, synthetic fixtures and DB snapshots. Historical reports, old commits and provenance references may retain factual descriptions of files that once existed; do not rewrite history or unrelated research exports. The local private build_ftp_graph.py is a reference artifact, **not** the production implementation; retire its assumption of packaged FTP input if it remains runnable, or clearly mark it obsolete without introducing a new FTP archive.

**Ordering is mandatory:** Gate 1 keeps files to support rehearsal; Gate 2 may remove them from the *unreleased branch* only after tests demonstrate the new database and explicit import method. Before deploying a package with no FTP files, the **currently designated production DB must already be bootstrapped and verified using the original inputs available from the old/staged release**. This is a controlled rollout, not normal auto-migration-on-page-load. Only then activate the new DB-only release and remove the active deployed FTP CSVs. Do not overwrite the production database with a stale test copy. An upgrade not yet bootstrapped must fail clearly, not show silently incorrect analytics. If cutover fails, restore the matching pre-migration code+database from the verified backup; do not discard newly edited DB history casually.

## 6. Verification and evidence required

### Gate 1: storage/consumer
1. On a consistent **private copy of the designated production data store plus required artifacts**, capture fixed-as-of/timezone baseline. Bootstrap exactly 66 known entries. Compare ordered values, numerical per-ride/daily Training State/Planning outputs and source choices **before and after storage-only migration**. Provenance, schema, cache bytes/signatures may differ; avoid claiming byte-identical result JSON. Verify cold/warm cache parity and restart stability.
2. Bootstrap failure matrix: malformed/inequal/wrong-digest source, missing path, duplicate dates, invalid dates/integers/intervals, conflicting nonempty store, partial transaction injection, uncertain transaction outcome, replay before and after edits/deletion, read-only/locked target, new genuinely empty store, uninitialized existing store and unsupported old/new schema.
3. Analytical oracle with synthetic measured-power rides and independently computed inverse-square stress, FTP date boundaries, source-date timezone/DST uncertainties, 42-/7-day recurrence, selection swap power/HR when FTP appears/disappears, deletion of last FTP, unchanged best-20/power curves/kJ/HR candidates. Verify current FTP and automatic Planning classification transitions, rider override precedence and unchanged literal target ranges/saved intents.
4. Confirm Home, Activity Review, Plan, Training State and selected Activity share consistent DB context, classifier cache rekeying and current numerical behavior; preserved sources/ids/sync/feedback/goals/tokens/source artifacts. Do not substitute activity counts for complete original artifact-manifest verification.
5. Measure a full-history cold recalculation cost and repeat warm request; performance optimization only with real evidence.

### Gate 2: editor/chart
6. Browser tests at desktop/mobile and keyboard/touch widths for orange, gray, unavailable and overlapping dot selection, exact blue entry markers, full history/date zoom/slider, ties/rounding, hover vs editing, manual add, edit, move, delete first/middle/last/only, before-first, date boundaries, same-day conflicts, two-tab stale revision, invalid nonce/Origin, cancel and restart persistence.
7. After each edit, new views of FTP comparison, Training State, Plan, Home and Activity Review consume updated history; numerical curves follow updated qualifying stress, observed work and performance readings unchanged. Previously confirmed intent context remains unchanged.
8. Check test and active tool dependencies, packaging/wheel contents, installed/deployed assets and live runtime lookup for all three FTP CSV files and legacy loaders. Validate a new Store with no historical FTP and a migrated production copy without CSV fallback. Do not require tests to use the Owner's original 66-row personal dataset as a permanent fixture.
9. Use separate private-copy database/artifact manifests before/after. Keep detailed rider/activity data, IDs, private screenshots, stores and backups local, never in Git. Publish only compact aggregate/synthetic evidence, reviewed commit, changed file list and test commands/results.

### Gate 3/4: live promotion
10. Present exact step-by-step production runbook and matching release/schema/backup pairing for Owner authorization. Stop application, nginx-backed traffic where necessary and sync writers; consistent SQLite backup with artifacts; confirm input and designated target; bootstrap and verify 66 in **current** production; activate DB-only code; confirm installed files absent; test normal page refresh/FTP read/Train State/Plan/Home/Activity and restart. Rehearse restore before executing. Roll back with matched code+DB, preserving upgraded state for investigation if edits already happened.

## 7. Stop conditions and non-goals

Stop if local checks conflict with this JIT, original 66 values or intended target cannot be proved, upgrade state is ambiguous, an FTP-dependent consumer is unhandled, concurrency or cache validity cannot be established, a private dataset could leak, or a product policy decision would need guessing. Escalate rather than bypass safety checks.

Out of scope: automatic FTP estimator/corrections, Strava writeback, new power modeling, retrospective inferred series, training model math changes, Planning workout-target scaling, Phase 6, enterprise audit/backup infrastructure, unrelated legacy cleanup, and source activity edits.

## 8. Acceptance

This task is done only when the Owner has inspected a working RideWorks FTP graph/editor, can manually set any earlier/lower/higher FTP entry from any eligible ride or by date, all consumers use SQLite and update correctly, imported observations and edits remain auditable in SQLite, original ride data remain intact, production has been promoted/restarted successfully, **all FTP CSVs are absent from active repository and deployed runtime**, and Analyst and Owner have accepted verification. Until then mark FTP-01 in_progress and keep the review gate explicit.
