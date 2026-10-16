# FTP-01 — Database-owned historical FTP and interactive comparison

**Status:** **Owner authorized bounded /AUTOTASK on 2026-10-15** for FTP-01 Gate 1 (SQLite storage/consumers) and Gate 2 (interactive chart/editor), with a distinct Astra technical-review pass at each SOFT boundary. Gate 3 remains HARD — Owner authorization for live promotion; Gate 4 remains separately authorized production cutover and HARD — Owner final acceptance. The Owner's single-history model supersedes earlier origin-specific/immutable-anchor and audit designs.
**Issue:** [#37](https://github.com/k14krug/rideworks/issues/37).
**Reviews:** [Initial Astra report](../../reports/FTP-01/astra-gate-0-review.md), [PR #38](https://github.com/k14krug/rideworks/pull/38); **[focused single-timeline review](../../reports/FTP-01/astra-single-timeline-delta-review.md), [PR #39](https://github.com/k14krug/rideworks/pull/39)**, accepted by Analyst. Migration, runtime-consumer, cache and verification cautions remain; source-based FTP categories and provenance/audit machinery are **not** product requirements.

## 1. Purpose and controlling product behavior

RideWorks has **one chronological history of FTP date/value entries**. The first 66 entries come from the existing approved Strava historical FTP record. They are the **starting data**, not a privileged or immutable class. **Every entry is simply a historical FTP value, regardless of whether it was imported or added later.**

The Owner's main workflow is **adding historical FTP values on previously unrecorded dates**, typically between existing entries, **but also before the earliest known FTP date** when an earlier qualifying ride gives useful evidence. An inserted entry takes effect on its date until the next existing entry; none of the existing values or dates are overwritten by insertion. A new entry can be *higher or lower* than neighboring history. Do **not** create original/supplemental categories, distinct marker styles or read-only locks based on origin, a second original-observation timeline, or an elaborate immutable edit audit trail. Small technical migration metadata and normal database safeguards are fine; users should not have to care about a source label.

Example: history Aug 1 = 130 W and Sep 15 = 170 W; Owner adds Aug 20 = 150 W. The one resulting timeline is Aug 1 = 130 W, Aug 20 = 150 W, Sep 15 = 170 W. August 20's value applies until Sep 15; both previous values remain as before. **Similarly, an earlier qualifying ride can inform a new date before Aug 1, making it the first known entry; dates before that remain FTP-unknown.** Repeat as desired. Gray or outlined-purple ride points are power evidence, **not** measured FTP; the Owner judges the value.

This direction **does not require a general edit/delete-any-entry UI in the first release**. Prior proposals for routine editing or deleting original settings and separate supplemental edits were exploratory assistant interpretations. Permit correcting or removing mistaken entries in a normal straightforward manner if needed for usability, but apply any such controls consistently; do not lock data according to whether it came from CSV. The required user-facing action is **adding an historical value on an unrecorded date (including before the first known date) without overwriting another entry**. If a material edit/delete product choice remains, stop for Owner clarification rather than manufacture an intricate audit system.

SQLite becomes the **only live authoritative source** of FTP for RideWorks. When safely migrated and promoted, remove all FTP CSVs from the final active code/deployment **with no archival FTP CSV**.

## 2. Requirements used

- Owner's 2026-10-14 RideWorks conversation, including latest explicit clarification that all historical FTP entries have the same status; no immutable "original" anchors or "supplemental" classes.
- [AGENTS.md](../../AGENTS.md), [product requirements](../PRODUCT_REQUIREMENTS.md), [Phase 4 acceptance](../PHASE_4_ACCEPTANCE.md), current Performance-v2 policy and running RideWorks UI.
- Source code: rideworks/store.py, training_state.py, training_state_page.py, planning.py, planning_page.py, home.py, performance.py, web.py, static performance/training_state JS, existing tests and source-aware verification tools.
- Approved historical 66-entry FTP input presently held in *two byte-identical CSV files*: data/athlete/strava_ftp_history.csv and rideworks/data/strava_ftp_history.csv, SHA-256 cb990c18e969d0d12f1d524bea22cf8b596746171f179f6241748394b87ad073. Retired root ftp-history.csv is a **different 52-entry legacy input; never use it**.
- Dex's 2026-10-13 standalone interactive comparison is UI reference, not runtime data. Counts such as 879/69/810 are a frozen report, not product invariants.

## 3. Execution Control

**Allowed Invocation: /TASK or /AUTOTASK.** Under /TASK, Dex stops at each gate; under /AUTOTASK, Dex may advance through Gate 1 and Gate 2 as SOFT gates only when the required verification and Astra review pass with no mandatory stop condition. Both modes stop at HARD gates. Follow AGENTS.md startup refresh, task-state, PR, security/privacy and mandatory-stop rules.

- **Gate 0 — HARD — Analyst (Astra): COMPLETED AND ACCEPTED.** Initial and focused design reviews were accepted in PRs #38 and #39. Do not repeat them absent materially new contradictory evidence.
- **Gate 1 — SOFT: SQLite history/storage and FTP consumers.** Implement the one-history SQLite table, explicit/bootstrap-safe initial import, durable initialization marker and replay protection, shared date-effective FTP lookup, coherent history/cache signatures across all consumers, and required synthetic/private-copy numerical and migration/restart verification. Keep FTP CSVs available during this gate. Have Astra perform the separate technical-review pass described below. If clean, /AUTOTASK may proceed to Gate 2; /TASK stops at this boundary. **No live production bootstrap/write, deployment, live CSV deletion, or chart work before Gate 1 review passes.**
- **Gate 2 — SOFT: chart/editor and retirement staging.** After Gate 1 passes, implement FTP History within Performance and manual intermediate insertion; run browser, accessibility, regression and private-copy tests. Stage FTP CSV/tool/package retirement **only in the unreleased task branch** while keeping the old release's approved import files available for eventual controlled promotion. Have Astra perform another separate technical-review pass. Resolve ordinary defects and re-review affected code. If clean, publish implementation PR, both review reports, full test evidence and a safe preview, mark ready_for_review and **STOP at Gate 3**; /AUTOTASK does not merge or deploy.
- **Gate 3 — HARD — Owner: working feature and live-promotion decision.** The Owner reviews the safe running preview, reports and exact live production runbook (designated store, source files, backup, matching-code rollback, validation and CSV removal). Owner's **explicit authorization for that live write/cutover** is required; code or visual approval alone is not blanket production-write permission. **/AUTOTASK must stop here**.
- **Gate 4 — controlled promotion; HARD — Owner final acceptance.** Start only after Gate 3 Owner authorization **and a separate Owner-directed invocation**; this is not an automatically crossable SOFT gate. Stop concurrent app/sync writers; make and verify a restorable database/artifact backup paired with its existing app version; bootstrap the designated actual live database while the approved original CSV inputs still exist; verify exact history/calculation parity; activate the DB-only release and only then remove FTP CSVs from the active checkout/package/deployment. Verify pages and restart; on failure stop and restore matched prior code + database, not an unsupported schema downgrade. Report final evidence and stop for **HARD — Owner final acceptance**, with Analyst involvement if technical issues need separate resolution. No task closure or merge claiming success without final approval.

### Required Astra second-pass technical review for EACH SOFT gate

Dex may implement using Astra, and may use Astra to review it, but the review must be a **distinct, fresh-context reviewer pass** rather than a quick self-certification in the coding context. Supply the reviewed commit, controlling JIT, actual diff, relevant source, tests and independent evidence; challenge missing FTP consumers, migration/replay/rollback hazards, cache/signature consistency, boundary/date behavior, UI accessibility, test omissions, privacy constraints and deviations from approved requirements as applicable.

Record the reviewer's model, exact reviewed branch/commit, findings, actions/fixes, test commands actually run, unresolved issues and final review disposition in a durable Gate 1 or Gate 2 report/PR section. Re-review meaningful corrections. **Same-model second-pass review is helpful but not independent external Analyst approval.** A gate passes only with affirmative review, all required verification and no unresolved material concerns. If a fresh-context reviewer cannot be run, a critical test fails or is inconclusive, or the reviewer raises a substantive issue, Dex must **stop for Analyst/Owner decision** rather than cross that SOFT gate.

Dex may fix ordinary implementation defects within authorized scope; stop for any AGENTS.md mandatory stop (changed product decisions, unexpectedly unsafe data conditions, scope expansion, broken invariants or unclear requirements). The JIT's classifications and acceptance criteria cannot be rewritten by Dex. Keep one FTP-01 task branch/PR with separate Gate 1 and Gate 2 evidence. **No live production database write, released CSV removal, deployment or unrelated Phase 6 work during the initial /AUTOTASK invocation.**

## 4. Gate 1 — SQLite history and complete reader migration

### Data model, effective dates and normal operations

- Use one small SQLite representation of date + positive integer FTP watts (stable identity if useful). **No per-entry source-type discrimination or shadow copies.** A technical migration completion marker may record that the 66-entry bootstrap has run, and a revision/signature tracks history changes for caches and stale form submissions.
- The single timeline sorts all entries by effective date. Each entry takes effect on its date (inclusive) until the next entry's date (exclusive); last extends indefinitely. An insert affects the intervening interval **without modifying the old entries**. Multiple equal-watt values with distinct dates are allowed.
- Reject a second entry on the same date; show the existing one rather than automatically overwriting it. If later providing correction to an existing entry, do so as an explicit action, never as a consequence of creating a new value.
- The Owner uses the established **America/Los_Angeles athlete calendar**. Preserve existing handling of activity timestamps with unknown source timezone (including FTP-date boundaries); the browser's local timezone must not silently move a candidate FTP date.
- **Owner's 2026-10-16 clarification:** allow adding a dated FTP **before the first existing entry**, including by selecting a purple "FTP unavailable" qualifying ride from that earlier period and adjusting its 95%-best-20 suggestion. The new entry becomes the earliest setting and applies from its date (inclusive) until the formerly earliest setting date (exclusive); FTP remains unknown before the new date. Reclassification and FTP-dependent training analysis for newly covered rides must update using the same cache/revision mechanism. Insertions between any two dates remain supported; no origin-based restriction or automatic inference/backfill. **After-last insertion is not part of this clarification** and remains an open future workflow choice, not a reason to block the earlier-date behavior. A genuinely new empty Store remains valid; zero-entry manual initialization is a separate question.
- A user can correct an accidental new entry if necessary, but do not build a large edit/audit service, and do not introduce irreversible "original" row protection as a product requirement. A straightforward undo/delete or explicit edit may be appropriate if narrow and tested; seek clarification if substantial scope is implicated.
- The whole history and any revision are read consistently within a SQLite transaction. A simple full-history signature in derived cache keys is acceptable until a measured performance problem warrants optimizing.

### Explicit bootstrap, rollout/recovery

- **Schema creation is not importing the 66 historical values.** New empty Stores get an empty valid history; existing production Stores awaiting the historical import require a clear migration-needed status, not silent empty-FTP analysis. **Persist that distinction at schema setup according to the pre-upgrade state; it must survive close/reopen and must not be inferred only from FTP row count.**
- Create an explicit bootstrap action with **specified source and target Store**; no automatic import from a packaged CSV on page view, no hardcoded permanent 66-row seed. While both approved files are still present, validate byte identity/known checksum, number/order/date/value/intervals before any DB write. Never import the obsolete 52-row root CSV.
- In one SQLite transaction insert exactly the 66 current history entries, import-complete marker and history revision, verify parity and commit. **Bootstrap replay checks the durable completion marker, not whether the current timeline still contains exactly the original 66 rows.** A completed replay is a no-op even after intermediate insertions/corrections; it must never restore/delete them. Detect conflicting/partial/unknown bootstrap states rather than silently merging. Validate source inputs before opening a target Store if construction could write schema changes.
- Perform all tests on synthetic Stores and a **consistent private copy** of the currently designated production DB+original artifacts. Maintain a complete restorable backup. The current deployed release may not understand the new SQLite schema; pair recovery DB and corresponding compatible code. No production bootstrap until explicit later Owner approval.

### All FTP consumers and calculations

Every active reader must resolve FTP from the same SQLite history and **a consistent history/revision snapshot taken inside the calculation transaction**. FTP-derived cache signatures must track that exact snapshot (not independently loaded history), while unchanged measured power and saved context remain intact:
- Training State per-ride power/session stress, selected method, per-ride training_stress_cache signatures, day-by-day Fitness/Fatigue/Form and Home Training State.
- Planning's completed history, current FTP, classification/cache, Activity Review context and Home/Plan summaries.
- Future confirmed intent context uses current FTP; existing confirmed intent snapshots, feedback, overrides/corrections remain historical records and **must not be rewritten**.
- Tests/diagnostic and installed runtime code must no longer depend on a packaged FTP history after cutover.

Lowering the effective FTP for an interval can raise power-derived stress; raising it can lower stress. HR-based *candidate* stress does not use FTP, but the selected model may switch if FTP availability changes. Preserve observed watts, best-20 history, power curves, work (kJ), power/HR source eligibility and original activity records. Rebuild daily Training State on new page requests using correctly validated per-ride caches. The existing hardcoded Planning target-watt ranges are a **separate policy** and do not change in FTP-01.

## 5. Gate 2 — graph and insertion workflow

Build an FTP History/Comparison view within **Performance** (with useful access from Training State), reusing RideWorks layout/interactions.

- Plot one **blue step line** and ordinary same-style blue date markers for every current FTP entry, with no origin-based display distinction. The rendered synthetic right endpoint is not a recorded historical setting. The line updates immediately after a new insertion.
- Source each 20-minute point from **performance.performance_history(store)** and its current *eligible and dated* points. Respect existing source signatures, pending/stale results and rebuild rules; do not use raw stale SQL, the frozen standalone HTML, or a new best-20 algorithm.
- Each dot's y-value and comparator use the **unrounded 0.95 × raw best-20 average watts**. Orange if strictly greater than effective FTP, gray if at/below (including ties). Show raw 20-minute watts and the computed figure in tooltips. The editable proposed integer FTP uses nearest watt, **round half up**.
- Eligible rides with unknown/uncertain FTP remain visible in a separately labeled **purple/outlined "FTP unavailable"** category, not mislabeled orange or gray. They are **selectable for an editable FTP suggestion**, including rides **before the earliest existing FTP**. Clearly explain whether a point is prehistory (no earlier known setting) or timezone/boundary uncertainty. A point's unavailable status only means it cannot currently be compared against a known FTP; it **does not prohibit using its measured 20-minute power as evidence**. For timezone-uncertain source dates, the Owner must deliberately confirm/adjust the effective calendar date; do not invent an absolute ride timestamp. On saving an earlier entry, reevaluate categories with the new history rather than freezing purple labels.
- Select any orange, gray **or purple/unavailable** dot to freeze the proposed date and adjustable watts. The Owner decides whether to add a historical FTP at that date; a gray or purple dot is not evidence of a definite FTP change. A manual date/value add independent of selecting a ride must also be available, including before the first known entry. Display existing FTP and **which interval would change**; require deliberate save, reject same-date overwrites, and show results on the graph. The FTP value can be increased or decreased relative to recorded history.
- Allow hover details, zoom/pan or equivalent genuinely usable date-range control, reset-to-all, show/hide dot categories, links to Activity, touch/mobile support, and keyboard/list selection of dense/overlapping points. Hover must not overwrite an in-progress edit. Preserve chart state when practical.
- Apply existing Origin/nonce/server validation conventions. Failed or stale submissions do not change FTP state. No automatic FTP estimation/update or Strava writeback.

## 6. Final CSV retirement

After verified migration and authorized cutover, **no FTP CSV is retained as active or archival user data**. Remove:
1. data/athlete/strava_ftp_history.csv;
2. rideworks/data/strava_ftp_history.csv;
3. obsolete root ftp-history.csv and its old loader if confirmed unused by current RideWorks.

Remove active CSV loader/package-data dependencies, change live test fixtures to synthetic SQLite history, update diagnostics and current documentation, and verify built/installable package has no FTP CSV. The private old graph-builder report is research only and must not remain a necessary runtime component. Historical Git commits/reports may truthfully mention the once-existing CSV files; that is not a new archive. Preserve other unrelated research CSVs and untouched original activity source data.

**Order:** Gate 1 keeps source CSVs; Gate 2 may stage removal only in an *unreleased* branch, with inputs still accessible from the old release. Bootstrap **the actual current production SQLite store** and verify it **before** deploying the final file-free code. No replacing that store with an older rehearsal copy. Roll back as a matched code/database pair.

## 7. Required verification

Gate 1:
- Exact 66 entry import parity, atomic bootstrap, marker/idempotent replay including after intermediate entry insertion, source checksum/malformed input and failure injection, schema-only interruption, missing/new/empty store handling, locking/restart and old-schema restoration on a consistent private copy.
- Synthetic insertion-between and **before-first** records with increasing/decreasing FTP, multiple dates, same-day rejection, equal watts on distinct dates, inclusive/exclusive date boundaries, browser zone and uncertain source times, and no mutation of existing rows when inserting. Verify a new first entry leaves preceding dates unknown, changes formerly purple eligible rides to comparative categories only where FTP is now known, and recalculates stress/cache/daily training state appropriately.
- Numerical equivalence before/after storage-only migration at fixed time/timezone; correct inverse-square power-stress changes after one insertion, unchanged raw watts, best-20/power-curves/kJ/HR candidates, and properly recalculated 42-/7-day Fitness/Fatigue/Form. Validate classifier cache/context, existing rider corrections, confirmed intents and every visible Training State/Plan/Home/Activity Review consumer.
- Compare original artifact manifests, activity evidence, identities, rider state, goals, feedback, sync and credentials on a private copy. Measure full-history cold/warm refresh. Do not commit personal activity data, DBs or source evidence.

Gate 2:
- Browser point selection (orange/gray/**purple unavailable including earlier-than-first**), manual date insertion including before first, **new-earliest interval preview**, integer rounding/ties, duplicate-date rejection, cancellation, two-tab stale changes, keyboard/overlap access, mobile/touch, zoom/date-range/legend behavior, focus and restart persistence. Verify no FTP is fabricated prior to the inserted new earliest date.
- New views after insertion show updated FTP on comparison, Training State, Plan, Home and Activity Review. Rebuild of selected FTP-dependent cached results is correct; existing entries, original rides, existing Planning intents and power records are untouched.
- Full regression, built/wheel/install checks without all three FTP CSVs or old runtime loader. Validate both brand-new empty SQLite and migrated-copy scenarios. Record source-neutral aggregate results.

Gate 3/4:
- Provide Owner-reviewed exact production promotion and rollback runbook, confirm explicit target store and source, stop concurrent writers, consistent backup, validated 66-entry bootstrap, DB-only app cutover, deployed CSV deletion, restart/cross-page smoke checks and any recovery actions.

## 8. Non-goals, stops and acceptance

No new physiological FTP prediction, automatic change, Strava writeback, Training State math overhaul, scaling Planning wattage targets, Phase 6, generic audit/athlete engine, or broad retired-Strava rewrite.

Stop for Analyst/Owner if historical entries are unexpectedly changed by insertion, bootstrapping would overwrite current data, migration/schema conflicts, private information would leak, a material design decision would be guessed, or a required gate is reached.

FTP-01 finishes only after: one SQLite history holds all imported and subsequently added values **without source-based categories**; the Owner can insert sensible lower/higher values **between existing dates or before the first known FTP** from the graph (including purple prehistory dots) or manually; all FTP-dependent views recalculate correctly; the existing dates/values remain intact when inserting; all FTP CSVs are removed from active app/deployment; controlled promotion and Analyst/Owner acceptance succeed.
