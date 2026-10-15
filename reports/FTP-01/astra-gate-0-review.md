# FTP-01 Gate 0 — independent Astra review

**Reviewer:** Astra, independent analyst (GPT-6 Astra), explicitly requested by the Owner.

**Reviewed:** 2026-10-14; branch `task/ftp-01-astra-review`, implementation/base commit `a85ff5ae41492c346a7386a61e0c5461526695a6`; `docs/tasks/FTP-01.md` at that commit. Lifecycle-only working edits to `TASKS.md` and `STATUS.md` were present.

**Disposition:** The objective is feasible and fits RideWorks. **The brief is not ready to authorize implementation.** Accept or amend the recommendations below, resolve the identified product/rollout choices, and have the Analyst commit a revised brief before a fresh `/TASK FTP-01`. This report neither changes that brief nor grants implementation authority.

## Review scope and evidence

I independently read the repository governance, current task/status, FTP-01 brief, controlling product requirements, Phase 4 acceptance, FTP provenance README, relevant current Python/JavaScript, tests, packaging and verification utilities. I fetched issue [#37](https://github.com/k14krug/rideworks/issues/37) with `gh issue view 37 --json title,body,comments,state,url`: it was open and had no comments. `gh pr list --state open --json number,title,headRefName` returned no open PRs. No unresolved review thread was available to incorporate.

I inspected the private graph builder as text, not by executing it. I inspected SQLite metadata/counts through `sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)`, `PRAGMA query_only=ON`, and a read transaction. I did not instantiate `Store`, invoke application pages, run calculations/tests, run migrations, copy the store, or change application/source data. Normal `Store` construction can migrate; normal analysis/page requests can write caches. Verification described later is proposed work, **not a claim of tests run**.

Observed local facts:

- `data/rideworks.sqlite3` reports schema version **10**, with **26 tables and no FTP table**. It contains 1,443 Activities, 1,419 Training State cache rows, 1,326 Planning classifier cache rows, one rider classification correction and zero saved planning intents. These are aggregate observations at review time, not permanent acceptance counts.
- The two specified FTP CSVs are byte-identical, contain **66 records**, and have SHA-256 `cb990c18e969d0d12f1d524bea22cf8b596746171f179f6241748394b87ad073`. I did not duplicate their records in this report.
- The private standalone HTML is approximately **4.8 MiB**. Its builder embeds Plotly and frozen comparison data. Its 879/69/810 counts describe that frozen comparison, not an invariant of current production.

The review follows PR-004 through PR-008, PR-012, PERF-001/004/005, STATE-002/003/004 and DATA-003/006. The Owner's new database-authority and CSV-removal direction supersedes the older packaged-file arrangement; it does not remove the historical-calendar, evidence and missing-data requirements.

## Required changes to the Analyst-controlled brief

| Priority | Required clarification/change | Why it matters |
|---|---|---|
| P0 | Specify the staged deployment/import/delete sequence and explicit production-write authorization point. Separate schema creation from Owner-specific bootstrap; specify uninitialized existing-store behavior. | Removing both files before the actual production import strands the only original input. A new empty schema is not evidence that the 66 rows were imported. |
| P0 | Define preservation of imported observations and edit/delete lineage inside SQLite, plus replay/idempotency semantics after user edits. | Mutable rows bearing an unchanged “Strava setting” label would misrepresent edited evidence; rerunning bootstrap must never restore deleted values or overwrite corrections. |
| P0 | Resolve graph cohort and numerical semantics: plot 95% of raw best-20, compare that unrounded value to dated FTP, and decide how eligible rides with unavailable FTP appear. | The reference excludes 150 prehistory rides, whereas the new brief says all qualifying rides. Raw best-20 versus 95% best-20 produces different orange/gray classifications. |
| P0 | Specify missing-history, before-first-date, deleting-first/last/all, date/calendar and collision behavior. | A genuinely new store must work without fabricated FTP; those same states become reachable through editing. The current loader rejects empty history. |
| P1 | Enumerate Home, Activity Review and immutable saved intent context alongside Training State/Plan, and require coherent FTP snapshots/signatures. | Changing only the two main pages misses visible consumers and historical evidence. |
| P1 | State numerical parity rather than byte-identical cache/JSON parity; add failure/concurrency/restart and deletion-of-last-entry checks. | DB provenance/digests and schema necessarily differ even when all calculations agree. |
| P1 | Define the CSV retirement boundary for active tooling, historical research, installed packages and documentation, including the private graph builder. | Removing tracked files alone leaves failing tests, tools and installed CSV runtime copies. A literal zero-match text search would also erase legitimate historical evidence. |
| P1 | Split implementation into two review gates, retaining final Owner visual/deployment acceptance. | Storage/correctness can be checked before interactive editing increases the surface area. The current gate numbering must be revised by the Analyst. |

These are requirements to make the plan executable, not permission for Dex to invent the answers. Concrete recommendations and the choices still needing approval follow.

## 1. Active consumers, caches and hidden dependencies

### Current runtime dependency map

| Component | Observed behavior and implementation implication |
|---|---|
| `rideworks/training_state.py:58` — `ftp_history` | Loads packaged CSV or caller-specified CSV, validates intervals, rejects empty history, returns raw-file digest. Replace runtime file ownership with an explicit store-scoped reader; do not retain an implicit packaged fallback. |
| `training_state.py:90` — `ftp_on` | Uses inclusive effective dates and a fixed `America/Los_Angeles` athlete calendar; withholds values near ambiguous source-date boundaries. Its source label is hardcoded to original Strava history, which must change for Owner adjustments. |
| `training_state.py:681` — `ride_results` | Reads FTP before entering its write transaction; per-ride signature includes selected FTP context **and the whole-file digest**. Cache is `training_stress_cache`; replacing the input must preserve deterministic invalidation and read consistency. |
| `training_state.py:764` / `daily_series` | Recomputes daily stress, Fitness/Fatigue/Form from per-ride results each request; there is no independent persisted daily-model cache to clear. |
| `rideworks/planning.py:119,227` — `completed_history`, `plan` | Completed history consumes `ride_results`; plan separately reloads current FTP. These must see one coherent history within a request. Projections are recomputed, not stored in a projection cache. |
| `planning.py:73` — `classify_activity` | Classifier signature already includes `result['ftp']` and `result['power']`; properly refreshed ride results invalidate it. Rider corrections in `planning_classifications` take precedence and must survive. |
| `planning.py:295` — `activity_context` | Independently reloads FTP and calculates the selected ride; this is an easy-to-miss third direct loader call. It can read a matching classification cache even with `cache_result=False`. |
| `planning.py:279` — `confirm_intent` | Stores current FTP and `ftp_source_sha256` in `recommendation_json`. These are historical recommendation inputs, not stale caches to rewrite on an FTP edit. Preserve existing snapshots; name/document new context fields appropriately. |
| `rideworks/home.py:158–163` | Home calls both `training_home` and `plan`: both visible cards must refresh after edits. Ordinary Home requests can populate caches. |
| `rideworks/planning_page.py:115` — `activity_panels` | Activity Review consumes `activity_context` and may call `plan` for next-ride context; verify both. |
| `rideworks/performance.py` / power curves | Best-20 and power-duration evidence do not depend on FTP. Preserve their measured values, eligibility, method and source identities. Join FTP at presentation/comparison time; FTP edits must not trigger source-power recalculation. |

The tracked root **`ftp-history.csv` is a third, legacy file: 52 two-column records, not either of the two equivalent approved 66-row interval CSVs**. `load_ftp_history.py:20` points to its old absolute location under the retired Strava project and parses watt/date pairs into `strava.models.FTPHistory`; no current RideWorks runtime reference was found. Do not bootstrap the new database from it or merge it with the approved history. The revised brief must explicitly settle its retirement: the named deletion scope covers two files, while the broader “FTP CSV files must disappear” direction could include this third file. Recommend removing the obsolete root CSV and its loader if the Analyst confirms that scope, without importing its contents or retaining another archive.

No additional live RideWorks current-FTP source was found by searching `rideworks/` Python/JavaScript. The retired `strava.models.FTPHistory`, `load_ftp_history.py` and `jobs/ctl_test.py` are a separate legacy SQLAlchemy application, not the production SQLite source. Do not migrate from that table or treat it as a compatibility requirement. The obsolete root loader should be explicitly retired or clearly excluded under the revised scope; no broad legacy refactor is needed.

### Dependency retirement inventory

Direct test dependencies include `tests/test_rideworks_training_state.py` (66-row/equality tests, interval tests, CSV override/cache invalidation) and `tests/test_research_training_state_ftp.py` (real CSV input). Replace the former with synthetic database histories and migration-specific checks; preserve the boundary/validation/math coverage. Research tests can use small synthetic inputs without retaining the personal source dataset in another format. Many integration tests create empty Stores and currently inherit packaged FTP implicitly: explicitly seed synthetic FTP where power stress/classification is expected, and keep separate no-FTP tests. This affects Training State, session power, Planning, Home/dashboard, Activity Review and web tests, not merely imports of `ftp_history`.

Schema-version expectations also occur in `test_rideworks_training_state`, `test_rideworks_planning`, `test_rideworks_strava`, `test_rideworks_performance`, `test_rideworks_dashboard` and power-curve migration tests. Update supported-version expectations while preserving old-version upgrade and rollback coverage.

Active tools that assume the old files or API:

- `tools/verify_planning.py`, `verify_planning_v2.py`, `verify_power_curves.py`, `verify_home_preservation.py`, `verify_activity_review_preservation.py`, `verify_rideworks_visual_preservation.py` hash both CSV paths.
- `tools/diagnose_training_state_power.py` and `diagnose_outdoor_training_state.py` directly call `ftp_history()`.
- `tools/verify_training_state_production.py` consumes `ftp_source_sha256`; session-selection verification compares FTP contexts. Review their output contracts rather than silently preserving a misleading file-source field.
- `tools/research_training_state_ftp.py`, `verify_training_state_ftp.py`, `report_training_state_ftp.py` belong to historical research; the verifier fixes a 66-entry expectation. Decide whether they remain explicitly historical tools accepting caller input, receive a DB snapshot adapter, or are retired. They must not remain required current verification against a removed path.
- The private `data/reports/ftp-vs-20-minute-2026-10-13/build_ftp_graph.py` defaults to the packaged CSV and asserts its digest/count. Treat it as historical reference; it is not a production builder after cutover. Do not commit the private report to solve this dependency.

`pyproject.toml` packages `data/*.csv`; remove obsolete FTP packaging. `data/athlete/README.md` and `rideworks/README.md` describe current file loading and need current DB instructions. Historical JITs, design reports and past verification hashes can retain explicitly historical references; the revised brief should distinguish these from executable/current instructions. Check actual wheel/install contents and deployment, not only `git ls-files` or an editable checkout. No archival replacement CSV, embedded 66-row Python/SQL/JSON seed, or private database belongs in the repository.

## 2. Migration, replay, rollback and empty stores

`rideworks/store.py:339–385` creates directories/connects and automatically applies schema migrations through version 10. It accepts only versions 0–10. Its migrations use their own `BEGIN IMMEDIATE`/`COMMIT`; `_transaction` at line 400 reuses an existing transaction. A schema-only migration and a data bootstrap must not accidentally create a half-imported “complete” state through mismatched transaction boundaries.

Recommended sequence for the revised brief:

1. With the CSVs still present, build the schema/model and an explicit, narrowly scoped bootstrap operation. Validate both source equality and the approved source fingerprint/count, ISO dates, positive integer values, distinct chronological starts and derived end boundaries **before import**. Preserve equal watt values on different dates.
2. Rehearse on a consistent private copy of the live database and required artifacts. Establish baseline calculations before changing that copy. No production writes follow merely from passing this rehearsal.
3. In one atomic bootstrap transaction, insert the 66 observations, effective records and provenance/import marker. Store source digest, source description, importer/version and timestamp. Verify exact ordered date/value parity. Distinguish schema-installed, bootstrap-complete and intentionally empty states; table existence or `COUNT(*)=66` is not a sufficient marker.
4. Replay of the same completed bootstrap is a verifiable no-op, **including after user edits/deletions**. A different source, nonempty unmarked history, partial/conflicting import or unexpected state stops without merging/replacing values. If the commit result is uncertain, inspect the durable marker; do not guess and reapply.
5. After the copy rehearsal and explicit rollout authorization, stop concurrent application/sync writers, take a consistent restorable production backup, bootstrap the actual designated production store while the sources are still available, verify it, then activate DB-only runtime. Only after that verified promotion remove both CSVs from the final checkout/package/deployment. The precise staging/commits and approval point must be written into the brief.

An existing unbootstrapped private store must not silently become an apparently valid empty-FTP installation when source files disappear. Recommend a clear migration-required preflight state for that upgrade path. A genuinely **new** store should create the schema with empty FTP history and no Owner-specific auto-seed. Explicit initialization/import state must let an intentionally empty history remain empty on restart. An empty final schema is valid; it cannot raise the current `FTP history is empty` exception.

Rollback requires an explicit code-and-data pairing. **The current code rejects schema 11 (or any other new version)**, so “revert the application commit” is not a working rollback plan. Prefer restore of the verified pre-migration database with the corresponding old application, while sources are still available during rollout. After user edits, restoring that old backup loses those edits and requires a deliberate recovery decision. Preserve new DB state before any recovery. Do not decrement `user_version` or discard tables as an improvised downgrade. Older installations/backups that missed bootstrap need a documented controlled recovery path; Git history can supply the original version when deliberately requested, but normal runtime must not fetch a dataset from Git or recreate an archival CSV.

This is a one-rider bootstrap, not a universal seed. The final migration/schema code can create empty stores without carrying the 66 records forever.

## 3. Effective dates, collisions and preservation of history

Observed existing contract: `data/athlete/README.md`, Phase 4 §6.1 and `ftp_on` agree on date-inclusive/next-date-exclusive intervals, last entry open-ended, no automatic prehistory backfill and the athlete calendar independent of browser timezone. The interval end is derived; **recommend storing starts and deriving ends** so insertion/deletion cannot leave contradictory interval fields.

The revised brief should explicitly approve the following semantics:

- Inserting between A and B splits A's interval; editing a date can alter both the old neighborhood and the new one. Preview both regions, not just the proposed start-to-next range.
- Same-date add is rejected with the existing entry exposed and a separate explicit edit action. Moving an entry onto another date rejects; no `INSERT OR REPLACE` or accidental merge. Multiple equal-valued settings on different dates remain distinct observations.
- Deleting a middle entry extends its predecessor; deleting the first creates unknown history until the new first; deleting the last extends its predecessor indefinitely; deleting the only/all entries produces no FTP. Preview these consequences and require an explicit delete action.
- A deliberately confirmed earlier historical entry is new Owner-supplied state. It does not infer a value before its own date or silently change all earlier rides. The brief should explicitly distinguish this authorized manual extension from forbidden automatic backfill.
- Calendar date defaults for selected rides must use the accepted athlete calendar, not JavaScript `toISOString().slice(0,10)` or the browser's current date. Preserve the existing unknown-timezone boundary rule, including adjacent distinct setting records with equal watt values; do not accidentally relax it while refactoring.
- Decide future-effective dates explicitly. The current schema/lookup concept can support them without applying them today, but the editor's validation and graph domain need a declared rule.

**Provenance is the main model gap.** “Preserve the exact 66 entries” and “edit/delete historical entries” are compatible if original imported observations survive separately from active selections. Recommend a compact FTP-specific original/import and revision record (or equivalent retained before/after history), with stable entry identity, action/time, source category and optional initiating Activity ID. An edited imported value must be labeled an Owner adjustment while still tracing to the original observation. Deleted entries leave active lookup but do not erase original evidence. A digest alone cannot reconstruct a deleted original record after CSV removal. This is a recommendation for Analyst approval, not authorization to build a generic audit service.

An initiating ride explains where an editable suggestion started; it does not make the saved number measured FTP. Retain enough method/source context to explain the 95% suggestion if the Activity's selected source changes later. Whether every successive Owner adjustment must be reconstructable, and the minimal retained fields, should be settled in the revised brief. Preserve historical planning intent snapshots rather than rewriting them to current FTP.

For preview/save consistency, recommend an expected history/entry revision token. Reject stale submissions with a reload/preview message; do not apply an old preview after another tab edits history. Validate integer-positive watts, canonical dates, referenced entry/activity, action and supplied fields server-side. An arbitrary physiological upper limit is a product choice, not something Dex should invent.

## 4. Chart source, comparator and UI reuse

Use **`rideworks.performance.performance_history(store)`**, not raw SQL across every row of `performance_history`, the frozen CSV report or a new best-20 algorithm. It filters policy/method, checks source signatures, excludes stale results and returns source provenance plus pending/stale counts. The local table contains multiple policies/results: its total row count is not the number of eligible current plotted rides. Continue established rebuild/retry behavior when results are pending; never plot stale best-20 merely to keep a dot count.

The private reference also includes **66 blue markers at the exact recorded FTP setting dates**, in addition to its step line (`build_ftp_graph.py`, the “Recorded FTP setting dates” trace). Preserve that Owner-requested dated-setting inspection in the proposed visual contract: markers should reflect the current active DB entries after edits, expose date/value/effective interval and provenance, and provide an accessible path to select the historical setting for explicit edit/delete. The synthetic step-line endpoint is not an actual setting and must not receive a setting marker. Counts must follow current history, not remain fixed at 66.

The private builder establishes an important distinction: its y-values and orange predicate are **`0.95 * average_watts`** and **that unrounded value > dated FTP**. The suggestion is then rounded for an editable integer entry. Using raw best-20 on the same FTP line, or rounding before classification, changes the meaning. Recommend explicitly adopting the reference formula, retaining raw best-20 in evidence, and specifying one shared tie/rounding rule for the editable default. Gray means comparable and at/below; it is not a low-confidence automatic FTP estimate.

The reference explicitly omits **150 eligible power rides before known FTP history**. The brief's “all qualifying ride points” and earlier-than-history editing need a decision: recommend retaining those rides as selectable points with an explicit **FTP unavailable / not comparable** visual state rather than falsely gray or orange. Alternatively, an explicitly approved comparable-only chart needs an independent path to add earlier/manual history. This is an Owner/Analyst choice; the review does not silently narrow “all.” Empty FTP must not make the editor inaccessible. Graph/history controls must also allow manual add/edit/delete without a qualifying ride on that date.

Practical reuse options:

| Option | Existing leverage | Additional work / tradeoff |
|---|---|---|
| Extend the native Performance SVG/chart patterns | `static/performance.js` already has ranges, all-ride points, source readout, keyboard traversal, responsive redraw and evidence pagination. Existing shell/forms/styles remain consistent. | Existing click/Enter navigates to Activity; editor selection needs deliberate separate actions. Current range buttons are not full pan/zoom/slider behavior. Need FTP steps, comparison classes, selection persistence and accessible controls. Preserve accepted rolling/month/year and Power Curve modes. |
| Use native Training State interaction patterns for a dedicated FTP comparison panel | `static/training_state.js` has selected-date/readout handling, touch and keyboard behavior; `power_curve.js` demonstrates mode/selection handling. No extra plotting runtime. | Neither is a drop-in scatter/FTP editor or full zoom/pan widget. Implement required navigation explicitly; do not claim existing range presets meet all reference interactions. |
| Integrate locally bundled Plotly | Private reference already demonstrates zoom, pan, range slider, toggles and rich tooltip layout. | Approximately 4.8 MiB private HTML combines runtime and data; do not embed it. Production would need a controlled local asset, live data/events, keyboard/form integration, accessible alternative and packaging review. Plotly is not in current `pyproject.toml` dependencies. |

Recommendation: reuse current native page/selection/forms and add a focused comparison view, provided the revised brief states exactly which zoom/period-navigation/slider interactions are acceptance requirements. If exact reference navigation materially reduces implementation risk, a separately justified local Plotly asset is an option. Do not impose it by copying the report or fetching a CDN runtime. Final placement and interaction tradeoffs remain Owner visual decisions.

Point selection must freeze the proposed ride/defaults while the user edits; pointer hover should not overwrite an in-progress form. Provide separate “open Activity” navigation. Dense/overlapping dots require keyboard/list access so “any dot” is not only a pointer hit-testing promise. Preserve selection by Activity identity across repaint, handle points that become unavailable, retain range/toggles after save, and label 95% as a starting suggestion rather than an estimator result.

## 5. Cache correctness and analytical consequences

The existing cache design is sufficient in principle: replace raw-file digest with a deterministic DB history/context signature, and include the selected effective entry/provenance. Read that history within the calculation transaction; `ride_results` currently loads it before the transaction, and `plan` separately loads it again. A coherent snapshot prevents mixed old/new FTP within a request. Mutation, revision recording and revision increment must commit atomically.

A simple global history signature will invalidate all Training State ride caches after any FTP edit, as the current file digest already does. This is acceptable for correctness if full-history refresh latency is measured; interval-targeted optimization is optional, not a prerequisite. Do not clear `planning_classifications`, `planning_feedback`, `planning_intents`, Performance or power-curve evidence. The Planning classifier already invalidates through FTP/power context; add explicit regression checks rather than assuming its dependency chain works after the API replacement.

For unchanged eligible power/duration, stress scales with **1 / FTP²** (`power_candidate` and `session_power_candidate`). Lower FTP can raise stress; higher FTP can lower it. HR candidate stress does not use FTP, and `power_candidate` records observed work before returning `ftp_unavailable`. Preserve those facts. Adding/removing FTP can change selected stress from HR fallback to power or back: **unchanged HR computation does not imply unchanged selected stress**. Deleting all FTP must leave HR-backed results usable and disclose unscored rides.

`daily_series` recursively updates 42-/7-day Fitness/Fatigue and start-of-day Form from the first usable score. Historical changes propagate beyond the edited interval, potentially through every later day; if the first usable day changes, initialization changes too. Preview should distinguish affected FTP/power-score intervals from downstream model consequences. Unless explicitly required, an honest interval/count explanation and next-page recomputation is sufficient; do not promise an exact model delta in a preview without computing it using the same rules.

**Planning target watts are a distinct existing policy.** `planning.py:146` (`recommendation`) returns literal coaching ranges by category; it does not receive current FTP or calculate these ranges from it. Changing the current-FTP display/history therefore does not automatically rescale the suggested workout watts. The brief should explicitly preserve these accepted ranges for FTP-01, or obtain a separate Owner/Analyst training-policy decision if rescaling is intended. Do not silently infer proportional scaling from “Planning must consume DB FTP,” and do not treat unchanged target watts as proof of a stale cache. Classification/rotation changes and target-range rescaling are separate behaviors.

Planning uses FTP-dependent observed stimulus and completed history to choose its rotation. It does **not** currently turn Training State Fitness/Fatigue into a new adaptive readiness algorithm. An edit may change automatic classification and recommendations, but need not change every recommendation (especially with rider corrections or Race metadata). Preserve those precedence rules and Phase 6 deferral. Old confirmed intent remains evidence of what was recommended/confirmed then.

## 6. Copy-store verification and privacy-preserving rollout

The revised brief should require these concrete checks after implementation authorization:

1. **Storage-only parity:** consistent private copy; fixed as-of/timezone; exact ordered 66-row import comparison and provenance marker; numerical per-ride/daily/Plan parity before and after. Compare relevant values/source choices, allowing only specified provenance/signature/schema differences. Cold recompute and warm cache must agree; restart must preserve DB authority.
2. **Migration failure matrix:** wrong/different sources, malformed intervals, duplicate dates, noninteger/nonpositive watts, missing source, nonempty conflict, injected mid-import failure, repeat import before and after edits, schema-only interruption, fresh empty store, old unbootstrapped store, unsupported version and read-only/locked destination. No partially committed records or misleading success marker.
3. **Editing boundary matrix:** add/insert/move/edit/delete; same-date conflict; repeated watts on different dates; delete first/last/only; before-first and approved future dates; unknown-timezone edges, DST and differing browser zones; stale preview in two tabs; invalid/missing entry/activity. Confirm failed saves leave history/revision/caches unchanged.
4. **Analytical oracle:** synthetic power with independently calculated inverse-square stress change; interval boundaries; downstream daily recurrence; unchanged raw best-20/curve/kJ and HR candidate values; power-to-HR fallback and reverse when FTP disappears/appears; all-FTP-empty behavior. Test classifier threshold crossings and persistence of rider overrides. Saved intent snapshots stay unchanged.
5. **Cross-page behavior:** after a save, new requests to Training State, Plan, Home and Activity Review use current DB FTP. No source CSV fallback. Test current FTP display, classification cache, pending Performance data and unchanged eligibility/source policies.
6. **Browser workflow:** select both orange/gray plus the approved unavailable state; ties/rounding; overlap keyboard alternative; date/watt editing; explicit collision and consequences preview; save/cancel/delete; reload/restart; mobile/desktop; zoom/navigation/toggles and focus; no unintended Activity navigation or hover overwrite. Reuse `web.py:676` Origin/nonce validation and request-shape/error conventions; exercise invalid Origin/nonce and malformed input.
7. **Preservation/privacy:** compare all pre-existing source/identity/state tables and artifact hash manifests on the copy, allowing only declared derived-cache writes. Retain corrections, feedback, intents, goals, sync/token state and source artifacts. Do not interpret counts of file-source rows as total originals; manifests must cover all artifact kinds. Keep detailed JSON, screenshots with private content, activity identifiers/names and store/backups local. Commit only synthetic fixtures and aggregate verification evidence.
8. **Final retirement/recovery:** run focused and full regression suites, build/install without either CSV, test a new empty store and a migrated-store copy, search executable/current documentation dependencies and inspect installed assets. Verify both files absent from the final active deployment, with no replacement dataset. Rehearse backup restoration with matching code before authorized live promotion. Do not run copy tools against the live default through an omitted path.

A consistent SQLite backup and explicit copy destination are preferable to copying a live DB file while writers run; account for artifacts as well as database state. For actual promotion, stop writers and restore/upgrade the current production store rather than overwriting it with an older rehearsal copy that has missed intervening syncs or user changes. No new backup infrastructure is necessary.

## 7. Recommended implementation gates and remaining decisions

**Two implementation gates are advisable.** This is sequencing within FTP-01, not two new product tasks:

- **Storage/consumer gate:** schema and provenance model; explicit bootstrap and empty-state behavior; store-scoped lookup; all Training State/Planning/Home/Activity consumers; cache correctness; synthetic tests and private-copy parity/recovery. Keep source CSVs available for controlled production bootstrap. Stop for Analyst review before UI work under `/TASK`.
- **Editor/chart gate:** approved live graph semantics, history controls, previews and protected mutations; browser coverage; private-copy end-to-end results; final deploy/removal package. Stop for Analyst review and Owner running visual/rollout approval. Production bootstrap and destructive live CSV retirement occur only at the explicitly authorized point.

The Analyst must reconcile these with the present Gate 1/2/3 labels and make clear whether production promotion is a post-acceptance mechanical step or a separately authorized final gate. The present wording requires CSV absence at completion yet prohibits live cleanup before approval; that is workable only with an explicit staged cutover. Passing Gate 0 does not authorize it.

Before rewriting the brief, Owner/Analyst decisions are needed on: unavailable-FTP graph membership/appearance; exact plot/rounding and navigation contract; whether future dates are allowed; minimal retained edit/original lineage; collision/confirmation and manual-entry behavior; page placement and preservation of exact-date blue setting markers; treatment of the third legacy root FTP CSV; whether literal Planning target ranges remain unchanged; and the precise live-bootstrap/delete/recovery authorization sequence. Recommendations above provide defaults for review, not settled policy.

Optional implementation improvements are limited: interval-targeted cache invalidation if measured refresh latency warrants it, and a richer numeric consequence preview if useful after the basic interval explanation is accepted. Neither a generic athlete-state framework, new adaptive planning logic, permanent duplicate source dataset nor Plotly dependency is required by this review.

**Gate 0 outcome:** independent review complete; publish this report, stop, and await accepted findings plus an Analyst-authored revised implementation brief and a fresh authorized invocation. No database, application, tests, migration, UI or FTP CSV changes were made in this review.
