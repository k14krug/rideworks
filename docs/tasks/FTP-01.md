# FTP-01 — Database-owned historical FTP and interactive comparison

**Status:** Owner clarified the product model on 2026-10-14. **Gate 1 is paused for a focused Astra check of this corrected brief**, and requires renewed Analyst clearance before further coding. The Owner's clarification supersedes the earlier "immutable original vs supplemental" design and the earlier general editing/audit design.
**Issue:** [#37](https://github.com/k14krug/rideworks/issues/37).
**Initial Gate 0 review:** [Astra report](../../reports/FTP-01/astra-gate-0-review.md), [PR #38](https://github.com/k14krug/rideworks/pull/38). Its migration, runtime-consumer, cache and verification findings remain useful; source-based historical FTP categories and provenance/audit machinery are **not** product requirements.

## 1. Purpose and controlling product behavior

RideWorks has **one chronological history of FTP date/value entries**. The first 66 entries come from the existing approved Strava historical FTP record. They are the **starting data**, not a privileged or immutable class. **Every entry is simply a historical FTP value, regardless of whether it was imported or added later.**

The Owner's main workflow is **inserting additional intermediate values between existing historical values**, informed by best-20-minute power and personal knowledge of training/recovery. A new entry takes effect from its date until the next existing entry; none of the existing values or dates are overwritten by insertion. The new entry can be *higher or lower* than the current historical FTP. Do **not** create original/supplemental categories, distinct marker styles or read-only locks based on origin, a second original-observation timeline, or an elaborate immutable edit audit trail. Small technical migration metadata and normal database safeguards are fine; users should not have to care about a source label.

Example: history Aug 1 = 130 W and Sep 15 = 170 W; Owner adds Aug 20 = 150 W. The one resulting timeline is Aug 1 = 130 W, Aug 20 = 150 W, Sep 15 = 170 W. August 20's value applies until Sep 15; both previous values remain as before. Repeat with additional dates as desired. Gray easy-ride performance dots are **not** measured lower FTP; the Owner judges the value.

This direction **does not require a general edit/delete-any-entry UI in the first release**. Prior proposals for routine editing or deleting original settings and separate supplemental edits were exploratory assistant interpretations. Permit correcting or removing mistaken entries in a normal straightforward manner if needed for usability, but apply any such controls consistently; do not lock data according to whether it came from CSV. The required user-facing action is **adding an intermediate historical value without overwriting another entry**. If a material edit/delete product choice remains, stop for Owner clarification rather than manufacture an intricate audit system.

SQLite becomes the **only live authoritative source** of FTP for RideWorks. When safely migrated and promoted, remove all FTP CSVs from the final active code/deployment **with no archival FTP CSV**.

## 2. Requirements used

- Owner's 2026-10-14 RideWorks conversation, including latest explicit clarification that all historical FTP entries have the same status; no immutable "original" anchors or "supplemental" classes.
- [AGENTS.md](../../AGENTS.md), [product requirements](../PRODUCT_REQUIREMENTS.md), [Phase 4 acceptance](../PHASE_4_ACCEPTANCE.md), current Performance-v2 policy and running RideWorks UI.
- Source code: rideworks/store.py, training_state.py, training_state_page.py, planning.py, planning_page.py, home.py, performance.py, web.py, static performance/training_state JS, existing tests and source-aware verification tools.
- Approved historical 66-entry FTP input presently held in *two byte-identical CSV files*: data/athlete/strava_ftp_history.csv and rideworks/data/strava_ftp_history.csv, SHA-256 cb990c18e969d0d12f1d524bea22cf8b596746171f179f6241748394b87ad073. Retired root ftp-history.csv is a **different 52-entry legacy input; never use it**.
- Dex's 2026-10-13 standalone interactive comparison is UI reference, not runtime data. Counts such as 879/69/810 are a frozen report, not product invariants.

## 3. Execution Control

**Allowed Invocation: /TASK only.**

- **Gate 0 — HARD — Analyst (Astra): initial review completed.** Owner subsequently clarified the core concept. **Before resuming Gate 1, Dex must refresh main and this JIT, report any code already written against earlier models, and use Astra for a *focused delta review* of the now-simple single-history, insert-between model.** Limit review to schema, bootstrap/replay, date semantics, caches and whether the revised contract is technically coherent. Publish the short findings and **STOP for Analyst authorization**. No repetitive full Gate 0 audit.
- **Gate 1 — storage/consumers, then HARD — Analyst.** Once explicitly reauthorized, implement the SQLite history, explicit/bootstrap-safe initial import, shared date-effective FTP lookup, required runtime readers and signatures, calculation parity and synthetic/private-copy tests. **No production bootstrap, live deployment, CSV deletion or chart UI implementation at this gate.**
- **Gate 2 — chart and manual intermediate insertion, then HARD — Analyst.** Only after Gate 1 review/authorization, implement the browser feature, tests and staged CSV/tool/package retirement on an *unreleased branch*. No live promotion.
- **Gate 3 — HARD — Owner authorization.** Owner inspects the running feature and explicitly approves the specific production-store migration/cutover plan. Code/visual approval by itself does not authorize a production write.
- **Gate 4 — controlled production promotion and final HARD — Analyst/Owner acceptance.** Stop concurrent writers, make/verify restorable backup with matching application version, bootstrap the designated actual live SQLite store while old approved CSV inputs are available, verify exact history and numerical behavior, switch to DB-only release, then remove FTP CSVs from active checkout/package/deployment. Verify pages/restart. On failure, restore matched old code **and** old DB, not an unsupported schema downgrade. Finish only after acceptance.

Dex must not revise these gates or silently proceed to a subsequent gate. Phase 6 and unrelated refactors are out of scope.

## 4. Gate 1 — SQLite history and complete reader migration

### Data model, effective dates and normal operations

- Use one small SQLite representation of date + positive integer FTP watts (stable identity if useful). **No per-entry source-type discrimination or shadow copies.** A technical migration completion marker may record that the 66-entry bootstrap has run, and a revision/signature tracks history changes for caches and stale form submissions.
- The single timeline sorts all entries by effective date. Each entry takes effect on its date (inclusive) until the next entry's date (exclusive); last extends indefinitely. An insert affects the intervening interval **without modifying the old entries**. Multiple equal-watt values with distinct dates are allowed.
- Reject a second entry on the same date; show the existing one rather than automatically overwriting it. If later providing correction to an existing entry, do so as an explicit action, never as a consequence of creating a new value.
- The Owner uses the established **America/Los_Angeles athlete calendar**. Preserve existing handling of activity timestamps with unknown source timezone (including FTP-date boundaries); the browser's local timezone must not silently move a candidate FTP date.
- Main v1 action: add a date within existing historical intervals, with a chosen higher or lower FTP. Avoid source-origin-specific "between original anchors" validation: users should not encounter different date rules depending on where the preceding entry came from. Adding before the earliest or after the latest available FTP record is not the primary request; don't invent values or backfill automatically. If that boundary action is necessary to complete an interactive workflow, surface a clear Owner decision rather than hard-code an "original imported" constraint. A truly new Store with no FTP history must remain valid and usable.
- A user can correct an accidental new entry if necessary, but do not build a large edit/audit service, and do not introduce irreversible "original" row protection as a product requirement. A straightforward undo/delete or explicit edit may be appropriate if narrow and tested; seek clarification if substantial scope is implicated.
- The whole history and any revision are read consistently within a SQLite transaction. A simple full-history signature in derived cache keys is acceptable until a measured performance problem warrants optimizing.

### Explicit bootstrap, rollout/recovery

- **Schema creation is not importing the 66 historical values.** New empty Stores get an empty valid history; existing production Stores awaiting the historical import require a clear migration-needed status, not silent empty-FTP analysis.
- Create an explicit bootstrap action with **specified source and target Store**; no automatic import from a packaged CSV on page view, no hardcoded permanent 66-row seed. While both approved files are still present, validate byte identity/known checksum, number/order/date/value/intervals before any DB write. Never import the obsolete 52-row root CSV.
- In one SQLite transaction insert exactly the 66 current history entries and an import-complete marker, verify parity and commit. Repeating bootstrap is a no-op; **it must not reset newly added intermediate entries or user corrections**. Detect conflicting/partial/unknown bootstrap states rather than silently merging.
- Perform all tests on synthetic Stores and a **consistent private copy** of the currently designated production DB+original artifacts. Maintain a complete restorable backup. The current deployed release may not understand the new SQLite schema; pair recovery DB and corresponding compatible code. No production bootstrap until explicit later Owner approval.

### All FTP consumers and calculations

Every active reader must resolve FTP from the same SQLite history and coherent snapshot:
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
- Eligible rides with unknown/uncertain FTP remain visible in a separately labeled unavailable category, not mislabeled orange or gray. They are inspectable; the availability of an "add" action follows the same date rules as any other ride, **not** the entry's import origin.
- Select any orange or gray dot to freeze the proposed date and adjustable watts. Gray does **not** imply FTP fell to the ride's value; the Owner decides. A manual date/value add independent of selecting a ride must also be available. Display existing FTP and **which interval would change**; require deliberate save, reject same-date overwrites, and show results on the graph. The FTP value can be increased or decreased relative to recorded history.
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
- Synthetic insertion-between records with increasing and decreasing FTP, multiple intermediate dates, same-day rejection, equal watts on distinct dates, inclusive/exclusive date boundaries, browser zone and uncertain source times, and no mutation of existing rows when inserting.
- Numerical equivalence before/after storage-only migration at fixed time/timezone; correct inverse-square power-stress changes after one insertion, unchanged raw watts, best-20/power-curves/kJ/HR candidates, and properly recalculated 42-/7-day Fitness/Fatigue/Form. Validate classifier cache/context, existing rider corrections, confirmed intents and every visible Training State/Plan/Home/Activity Review consumer.
- Compare original artifact manifests, activity evidence, identities, rider state, goals, feedback, sync and credentials on a private copy. Measure full-history cold/warm refresh. Do not commit personal activity data, DBs or source evidence.

Gate 2:
- Browser point selection (orange/gray/unavailable), manual date insertion, preview, integer rounding/ties, duplicate-date rejection, cancellation, two-tab stale changes, keyboard/overlap access, mobile/touch, zoom/date-range/legend behavior, focus and restart persistence.
- New views after insertion show updated FTP on comparison, Training State, Plan, Home and Activity Review. Rebuild of selected FTP-dependent cached results is correct; existing entries, original rides, existing Planning intents and power records are untouched.
- Full regression, built/wheel/install checks without all three FTP CSVs or old runtime loader. Validate both brand-new empty SQLite and migrated-copy scenarios. Record source-neutral aggregate results.

Gate 3/4:
- Provide Owner-reviewed exact production promotion and rollback runbook, confirm explicit target store and source, stop concurrent writers, consistent backup, validated 66-entry bootstrap, DB-only app cutover, deployed CSV deletion, restart/cross-page smoke checks and any recovery actions.

## 8. Non-goals, stops and acceptance

No new physiological FTP prediction, automatic change, Strava writeback, Training State math overhaul, scaling Planning wattage targets, Phase 6, generic audit/athlete engine, or broad retired-Strava rewrite.

Stop for Analyst/Owner if historical entries are unexpectedly changed by insertion, bootstrapping would overwrite current data, migration/schema conflicts, private information would leak, a material design decision would be guessed, or a required gate is reached.

FTP-01 finishes only after: one SQLite history holds all imported and subsequently added values **without source-based categories**; the Owner can insert sensible lower/higher intermediate values from the graph or manually; all FTP-dependent views recalculate correctly; the existing dates/values remain intact when inserting; all FTP CSVs are removed from active app/deployment; controlled promotion and Analyst/Owner acceptance succeed.
