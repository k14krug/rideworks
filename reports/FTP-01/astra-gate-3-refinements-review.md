# FTP-01 Gate 3 refinement technical review

**Reviewer:** Astra, distinct fresh-context technical-review agent (`astra_ftp01_gate3_review_final`).
**Scope:** The four Owner/Analyst Gate 3 refinements on draft PR #41. This review does not repeat Gate 0 or recertify Gates 1/2, authorize production access, or constitute Owner visual acceptance.
**Controlling sources:** `origin/main` at `c748ef90fc9a64959c2facb7eb7aa55683ef8ced`, its `docs/tasks/FTP-01.md` (PR #42), PR #41's Analyst concurrency review and both October 16 Owner clarification comments, repository governance and the relevant historical-state requirements.
**Reviewed branch/base:** `task/ftp-01-implementation`, base HEAD `5f33c1bf8b69aeb73313e75ba3a71ad8fe0c1543`, with uncommitted refinements. Initial reviewed implementation/test/tool patch SHA-256 (`git diff --binary -- rideworks tests tools | sha256sum`): `6a5690d6e3fc3921f7f844f87a3b172545d0992fe32fdf95ca3e5fddec035a02`. **Final corrected patch SHA-256:** `11acedef08c3efda59b96bbe66434520af8344449e42d8ae56c5338e7698885f`, using the same command and base. This identity excludes reports/status documentation, so subsequent publication edits do not imply a different code review.

## Findings and required actions

1. **Material concurrency defect found in Home — resolved.** The individual Training State and Plan routes now batch writes after their calculations, but Home originally called `training_home` before `plan`. Its stress-cache batch therefore acquired WAL's writer slot before the subsequent classification loop. An independent two-ride synthetic GET `/`, paused during the second classification, made a concurrent FTP insertion fail with `database is locked` after 0.1008 seconds at a 100 ms busy timeout; the GET subsequently returned 200. The correction runs Plan first, finishing stress and classification calculations before flushing the batches; Home then consumes the already populated stress cache for its Training State summary. The visual ordering and coherent outer request transaction are preserved. I reviewed this correction and independently ran the added cold Home regression: the concurrent FTP write succeeds while classification two is paused, the stale GET retries, and only current-FTP signed results remain cached.
2. **Requested prehistory integration regression missing — resolved.** The earliest-entry unit test covered timeline boundaries, preservation, collision and stale revision, but the initial tests did not establish the requested analysis transition. The added synthetic integration regression now proves that a previously purple ride changes from unavailable to the at/below category at an exact 190 W comparison tie, changes its selected stress method to power, changes stress and daily model values, updates Plan's FTP and both cache signatures, preserves existing entries, and leaves dates before the new first setting unknown. I reviewed and independently ran this test successfully.

## Confirmed refinements

- The backend permits a new first entry without altering existing date/value rows, retains unknown-before-first semantics, and continues rejecting duplicate dates, stale revisions, after-last extension and empty-history initialization. The editor describes the affected earliest interval. Unavailable dots explain prehistory versus uncertain-date causes; `date_uncertain` selection leaves the date blank for deliberate entry.
- Visible ride radii are 2.7 SVG units with separate 10-unit transparent hit targets. Blue FTP markers remain distinct. Point keyboard activation and paginated list selection remain available.
- Navigator keyboard movement now uses inclusive date values consistently: each arrow moves one day, Home/End clamp to valid full/one-day bounds, and numeric ARIA values/limits track the current dates. Pointer mapping accounts for the actual SVG x=60..970 track. Exact controls, navigator and draft preservation passed independent browser checks.
- Deferred GET transactions plus WAL allow concurrent writes during read calculations. Training State, Plan and the corrected Home regression tests independently passed, including fresh-snapshot retry and current-FTP signed cache batches. WAL-aware inventory operates on a verified private copy when sidecars exist; the source-preservation regression passed. The runbook now calls out WAL and SQLite backup handling. The bounded retry is demonstrated for a concurrent committed writer; it is not a promise that repeated contention or an indefinitely held writer can never fail.

## Independent verification actually run

All Python fixtures used temporary synthetic stores. Browser checks used only the designated isolated preview, and submitted no FTP entries. No production database was opened.

```sh
env -u DEBUG PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -m unittest test_rideworks_ftp_history test_rideworks_ftp_page test_rideworks_calendar_defaults
# 26 tests passed
env -u DEBUG PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -m unittest test_rideworks_training_state test_rideworks_planning
# 60 tests passed
node --check rideworks/static/ftp.js
git diff --check
# both passed
env -u DEBUG PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -m unittest test_rideworks_ftp_history test_rideworks_ftp_page test_rideworks_calendar_defaults test_rideworks_training_state test_rideworks_planning
# Bounded re-review after corrections: 88 tests passed in 4.129 seconds.
# Includes the two newly added regression tests.
```

The independent Home reproduction used the same two synthetic 1,200-second FIT rides as the existing Plan concurrency fixture, GET `/`, a pause after classification two, and a second connection's `add_entry` with `PRAGMA busy_timeout=100`. Result: writer failure described above. This check is distinct from the submitted `/plan` regression.

Using the Playwright skill and Chromium, a separate local review script (`/tmp/ftp-astra-browser.js`) was run with `npx --package @playwright/cli playwright-cli -s=astra-ftp-review run-code --filename /tmp/ftp-astra-browser.js`: **21 assertions passed**. It checked navigator arrows/Home/End, inclusive one-day clamping, live numeric/readable ARIA, exact pointer track endpoints, draft date/watt preservation, reduced radius and hit target, keyboard prehistory selection/save availability, and document fit at 1280/768/390/320 px. No save was submitted. The parent-reported 107-check browser suite and initial 492-test suite were reviewed as evidence, not claimed as independently rerun here. The final corrections affect Home ordering and Python regressions, not the already checked navigator code.

## Disposition

**TECHNICAL PASS for the corrected Gate 3 refinements.** Both material findings from this pass are resolved and independently verified; no unresolved material technical concerns remain in this scoped diff. The implementation is suitable to return for Owner preview and the separate live-promotion decision. This is a fresh-context technical review, not external Analyst acceptance or Owner visual approval. Gate 3 remains HARD — Owner; no production migration, deployment, merge, or active CSV removal is authorized.
