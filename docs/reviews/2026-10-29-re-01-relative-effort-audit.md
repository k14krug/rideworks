# RE-01 — Relative Effort release-readiness and source-calibration audit
**Analyst first pass:** 2026-10-29. **Status:** review requested; no model change or release authorization.

## What is actually implemented

The Owner reported colored dots formerly visible in Home's Recent Activities and in the Activities browser. They are **real dev-branch features**, not a lost mockup:

- `rideworks/home.py` renders `home-effort-dot effort-{slug}` from the shared `relative_effort.for_store` result.
- `rideworks/web.py` renders the `Relative Effort` column with `relative_effort.chip()` and the Ride Details `relative_effort.card()`.
- `rideworks/static/style.css` defines five category colors plus gray unavailable.
- `rideworks/relative_effort.py` contains the versioned `relative-effort-v1` model.
- `tests/test_rideworks_relative_effort.py` tests 42-day history, six prior rides, boundaries, midrank ties, one-band intensity adjustment and unavailable data.

Controlling design: [RE-01](../design/RE-01-relative-effort.md). This is already a development prototype, **not production accepted**.

## Branch and release finding

At inspection, `main` and `dev` had **diverged**: `dev` was 92 commits ahead and 43 behind `main` (merge base `dcd77f1`). `main` does not contain `rideworks/relative_effort.py`. Do **not** simply merge all of `dev` into `main` to restore these dots. First choose a controlled code/data-compatible promotion with an explicit Owner gate. The screenshot cannot, by itself, establish which checkout and runtime currently serves the displayed page; determine that on the actual host.

Engineering follow-up [PR #46](https://github.com/k14krug/rideworks/pull/46) was accepted and merged into `dev` on 2026-10-19. Its report says 529 Python tests and 27,990 Chromium assertions passed, including Relative Effort colors and related UI behavior. This is **reported historical verification**, not a fresh test performed in this review. Current dev `STATUS.md` explicitly reserves mixed-source calibration and final development/production UI acceptance for the Owner.

## Existing scoring rule, verified by source inspection

1. For each cycling ride with eligible whole-session stress and its supported active duration, compare with eligible rides in the **previous 42 Los Angeles calendar days**; exclude same-day/future/unknown-date rides.
2. Require at least **six** eligible prior rides, else display **Not rated** with a reason.
3. Compute empirical midrank percentiles independently for selected modeled stress (load) and stress per supported active hour (intensity).
4. Map percentile quintiles to Very Light / Light / Moderate / High / Very High.
5. Overall starts with load; boost only **one band** when intensity is at least two bands higher. This is a RideWorks heuristic, **not** an external physiological standard.
6. A power-derived value, estimated whole-session power value, and HR-derived stress can enter the same ranking. Provenance stays attached and partial-only stress is not rated.

The UI uses relative-history categories, **not absolute intensity zones**, and cannot infer perceived exertion directly.

## Open calibration issue

The `HOME-DEV-REVIEW` JIT reports that comparing only within matching method families changed **120 of 857** formerly classifiable ratings; one example moved Very Light -> High. That finding raises concern but does **not** establish that either policy is correct. There may also be fewer eligible historical comparisons when cohorts are separated.

To separate actual category shifts from the loss of available comparison rides, this branch adds a **non-production sensitivity diagnostic**:

- `tools/relative_effort_sensitivity.py` calls the accepted `classify()` unchanged against the full historical population, then repeats classification with (a) power / estimated session-power together versus HR; (b) exact method categories separately.
- Reports total input by source method, available/unavailable counts, comparable labels, higher/lower changes, differences of two or three bands, and aggregate transition counts.
- Contains **no activity identifiers, titles, per-ride dates, power values, FTP entries, or location data** in its output.
- Does not alter rating code, Training State, cached results, historical sources, schema, or UI.
- `tests/test_relative_effort_sensitivity.py` adds synthetic checks for same-method stability, mixed-source large shifts, insufficient-family history, family vs exact grouping, and aggregate output privacy.

**Important:** This is a diagnostic, not a proposal to split cohorts in production. Separating stress families can improve conceptual comparability but may drastically reduce coverage and historical stability. Simply changing the algorithm would replace one assumption with another.

## Dex independent review / local verification

1. Refresh origin and review this branch **against current `dev`**, not against an old `main` commit. Read `AGENTS.md`, RE-01, this note, the diagnostic, its tests and HOME-DEV-REVIEW source/evidence.
2. Check the Python implementation for correctness, privacy, cohort eligibility, source-family grouping, 42-day/same-day boundaries, effective FTP and active-duration semantics. Challenge the assumption that `power` and `session_power` belong together.
3. Run focused tests against the branch:
   ```bash
   DEBUG=0 .venv/bin/python -m unittest discover -s tests -p 'test_relative_effort_sensitivity.py' -v
   DEBUG=0 .venv/bin/python -m unittest discover -s tests -p 'test_rideworks_relative_effort.py' -v
   ```
   Report actual output and failures. No test result is claimed by this Analyst session.
4. Using a **verified disposable private Store snapshot**, not the authoritative live data directory, run:
   ```bash
   DEBUG=0 .venv/bin/python tools/relative_effort_sensitivity.py \
     --data-dir /path/to/disposable/rideworks-copy \
     --as-of 2026-10-29T12:00:00-07:00
   ```
   Ensure the copy contains matching SQLite and referenced originals and that no concurrent active writer uses that copy. `Store` initialization may perform normal directory/SQLite housekeeping; do not treat the script as safe on the live Store. The `ride_results(..., cache_writes=[])` diagnostic path intentionally avoids flushing stress caches.
5. Examine denominators: baseline rated, both-rated, newly unrated, and changes **only within the both-rated population**. Break out power, session power, and HR. If counts differ from the earlier 120/857 check, explain as-of, cohort definitions, data changes and denominator before calling it a regression.
6. On the existing **development app** verify colored indicators on Home, Activities and Ride Details, as well as Not rated tooltips/labels and accessibility at desktop/mobile. Verify the running checkout/commit explicitly; never infer it from a screenshot alone. No restart of live processes without Owner instruction.
7. Report findings as review comments on this PR. If a logic defect is found, describe a minimal correction and test; **do not alter production rating policy or deploy**. The final calibration choice and release remain HARD — Owner decisions.

## Boundaries and disposition

- **No production deployment, `main` merge, real-data edit, Strava sync, or model recalibration.**
- This audit is source inspection and a proposed reproducible experiment. There is no access here to the user's local dev/prod server, private ride database or full browser test environment.
- Dex's independently reproduced synthetic and real-data results, plus the Owner's visual and calibration judgment, are required before declaring RE-01 production-ready.
- If a small safe fix becomes necessary, prepare a separately reviewed change. Do not hide a new effort model in a review-only task.
