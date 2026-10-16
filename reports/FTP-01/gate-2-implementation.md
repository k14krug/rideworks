# FTP-01 Gate 2 implementation and verification

The Performance FTP History view now shows one blue step line with markers at actual entry dates and every current eligible dated 20-minute result. Orange/gray comparisons use unrounded 95% of raw power; unavailable FTP remains a separate selectable category. All 879 comparable results from the reference are present, plus 150 results without usable historical FTP in this snapshot. Frozen report counts are not application invariants.

Selecting a ride freezes an editable date/watt suggestion (nearest watt, half up). Manual intermediate insertion previews the affected interval, rejects same-date overwrites and stale revisions, and requires a deliberate protected POST. Existing entries remain unchanged. Date-range and category controls persist across save; keyboard/list and touch selection support overlapping points. Blue entry markers render above ride dots. First-release scope is insertion; no general edit/delete UI, extrapolation or automatic FTP correction is introduced.

## Verification actually run

- `DEBUG=0 /home/kkrug/projects/rideworks/.venv/bin/python -m unittest discover -s tests`: **488 passed**, 29.972 seconds on 2026-10-16. Includes synthetic FTP comparison/form security, exact ties, half-up suggestions, athlete/calendar boundaries, empty history, collision and stale rejection, atomic bootstrap/replay and migration interruption. Earlier Gate 2 implementation run also passed 488 tests.
- `node --check rideworks/static/ftp.js`: passed.
- `npx --yes --package @playwright/cli playwright-cli -s=ftp01 run-code --filename tools/verify_ftp_browser.js`: **70 browser assertions passed** on a disposable private copy. [Aggregate evidence](gate2-browser.json). Verified 1,029 points, initial 66 markers, 69 orange/810 gray/150 unavailable, toggles, single-day range/reset, keyboard selection, preserved draft on hover, collision preview, manual save, existing-row preservation, repaint, two-tab stale rejection, reload, five cross-page routes, no JS errors, widths 1440/768/390/320, and touch selection in an Asia/Tokyo browser. The trial insertion took only the disposable copy to 67 entries.
- Isolated wheel build with `python -m pip wheel --no-deps . --wheel-dir local_data/ftp01/wheels`: passed. ZIP inspection verified no CSV files and exact current FTP JS. An independent venv installed the wheel and ran from `/tmp`; explicit 66-entry bootstrap and migrated FTP view passed, as did Home/FTP History/Training State/Plan on a genuinely empty Store.
- `tools/verify_ftp_history_private.py` against that installed package reproduced both fixed-clock/timezone baseline scenarios and six page renders, preserved all 24 non-cache tables and 1,422 artifacts, and matched warm caches. [Package parity evidence](gate2-package-parity.json). Initial recalculation 21.25 seconds; warm refresh 0.56 seconds.
- All original active-checkout FTP CSV hashes and the production database hash remain unchanged. The two private settings/OAuth recovery sidecars were copied and hash-verified only into protected recovery copies; no credentials are present in the preview copy. No private activity payloads, snapshots, screenshots or databases are committed.

## Ordinary defects found and corrected

The first UI probe caught an incorrect `safe_json` import; it was corrected before the passing suite/browser run. The browser verification itself initially waited for a hidden JSON script to become visible; its wait now checks attachment after completed navigation. Wheel build initially used an old local build backend; rebuilding with normal isolated build requirements succeeded. These were ordinary implementation/verification defects, not changed product rules or weakened checks.

## Retirement and recovery boundary

Only the **isolated unreleased task checkout** stages deletion of the three FTP CSVs and the unused retired loader. Package-data no longer includes CSVs; synthetic tests replace personal source dependencies; active verification tools use database snapshots and retain the unrelated Elevate benchmark. Historical research tools accept explicit caller inputs and remain documented research, not runtime loaders. No duplicate FTP dataset or replacement archive was added.

The active checkout `/home/kkrug/projects/rideworks` remains on the old release with all three source CSV files available. The [proposed runbook](promotion-runbook.md) requires explicit Gate 3 authorization and a separate invocation before actual live bootstrap, deployment or active CSV removal. Preview copies will be reset to the original 66-entry timeline after destructive browser trials; they are never a production replacement.

## Gate boundary

A distinct fresh-context Astra technical review must be affirmative before this SOFT gate passes. Its exact reviewed commit, commands, findings and any fixes are recorded in the separate Gate 2 review report. Stop at Gate 3 — HARD Owner. These tests do not constitute live deployment or final acceptance.
