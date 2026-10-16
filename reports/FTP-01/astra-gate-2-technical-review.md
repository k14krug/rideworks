# FTP-01 Gate 2 technical review

Reviewer: **GPT-6 Astra (orchestrator-selected `gpt-6-astra`, fresh context)**. Distinct second-pass technical review; not external Analyst acceptance.

Reviewed branch: `task/ftp-01-implementation`. Exact reviewed commit: `832eac0a0e3262cbfb83675734b29d6319925ca7`. Gate 2 diff base: `3a1b482`. PR: #41. Review date: 2026-10-16. The proposed `promotion-runbook.md` was also supplied as review input. Gate 1's affirmative review at `662e954` is context, not repeated certification.

## Disposition

**PASS — affirmative Gate 2 technical review.** No unresolved material findings; no code fixes required or made. The chart/editor and unreleased retirement staging satisfy the Gate 2 contract together with the supplied browser, private-copy and installed-package evidence. Finish the required PR/evidence/preview bookkeeping, then **STOP at Gate 3 — HARD Owner**. This review does not authorize merging, production writes, deployment, deletion from the active old release, or task acceptance.

## Examination and findings

Read AGENTS.md, FTP-01, relevant product/Phase 4 requirements, current status, prior Gate 1 review, actual Gate 2 diff, comparison/editor/server code, shared snapshot/insertion/lookup and Performance source paths, tests, browser verification script, retirement/package configuration, implementation report and aggregate browser/package evidence. PR #41 currently reports no comments or reviews.

- **Evidence and calculation: pass.** Comparison calls `performance_history(store)` within the FTP snapshot transaction; eligibility, missing dates and stale signatures retain the existing Performance rules. All supplied eligible dated points are carried through, with unavailable FTP separately labeled. Comparator and plotted value use unrounded 95% of raw best-20 watts; integer proposals use decimal half-up. Exact ties are gray. Absolute timestamps use America/Los_Angeles, and unknown-timezone records retain established uncertain-boundary semantics.
- **Graph and interaction: pass.** One source-neutral blue step history has markers only at actual settings; synthetic line endpoints do not acquire markers. Ride categories, date-range/reset controls, paginated keyboard/list selection, activity links, touch selection, editable frozen suggestions and manual insertion are implemented. Hover changes inspection text without replacing the draft. Preview identifies the effective interval and existing FTP; collision handling never overwrites. Empty history and out-of-range candidates remain inspectable with explicit unavailable insertion guidance. No general edit/delete or source-origin classification was required.
- **Protected mutation and consumers: pass.** Origin and nonce checks precede insertion; parser rejects duplicate/unexpected fields. Server date/value validation, stale revision rejection and SQLite transaction preserve old rows. A successful POST redirects to a fresh comparison. Existing Gate 1 snapshot/cache integration remains the common path for Training State, Planning, Home and Activity Review; this diff introduces no second FTP authority or changed power algorithm. Supplied cross-page browser evidence establishes successful renders, while the numerical/cache preservation evidence and Gate 1 verification establish the calculation behavior.
- **Retirement and privacy: pass for unreleased staging.** The three FTP CSVs and unused legacy loader are removed only in the task branch; package data is static assets only. Active diagnostics now use Store history, and tests use fictional generated inputs rather than a retained personal seed. Explicit bootstrap remains available for controlled promotion using the old release's approved sources. No new personal dataset/archive, database, credentials or activity payload is introduced by the reviewed diff.
- **Promotion proposal: appropriate gate boundary.** The runbook requires reconfirming the actual store/running code, stopping writers, a verified matched code/database/artifact/sidecar backup, bootstrapping the actual current store before DB-only activation, parity checks and matched rollback. It explicitly requires Owner authorization and a separate invocation. Actual launch details, approved final commit and backup location must be recorded at that later gate; this proposal is not an executed production command record.

Severity findings: **none requiring correction**. Actions/fixes: none. Unresolved material concerns: none within Gate 2.

## Independent verification actually run

Working directory: `/home/kkrug/projects/rideworks-ftp01`. The protected original checkout was not modified and no default/live Store was constructed.

```bash
DEBUG=0 /home/kkrug/projects/rideworks/.venv/bin/python -m unittest discover -s tests
node --check rideworks/static/ftp.js
gh pr view 41 --json comments,reviews
```

Results: **488 tests passed**, 30.061 seconds; JavaScript syntax passed; PR comments/reviews empty.

An additional `DEBUG=0 PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -` probe used an explicit `TemporaryDirectory` Store and fictional settings (2020-01-01: 190 W; 2020-12-31: 220 W). It verified duplicate/unexpected POST fields, invalid dates, same-date collision and before/after-range attempts all return 400 without changing the snapshot. A valid June 1 insertion returned 303, survived reopening, incremented revision once and preserved both existing entries. Mocked eligible Performance evidence at `2020-06-01T06:59:59+00:00` and `07:00:00+00:00` verified the Los Angeles midnight transition: May 31 uses 190 W and gray equality; June 1 uses the new 180 W and orange. Result: **PASS**.

## Supplied evidence and limits

Reviewed, rather than independently reran, the disposable-copy browser run: **70 assertions**, 1,029 points (69 above, 810 at/below, 150 unavailable), 66 original markers, one test-only insertion, range/category/keyboard/touch/stale-tab/reload behavior and widths 1440/768/390/320 including Asia/Tokyo. Counts describe this snapshot, not application invariants.

Reviewed the installed-wheel/private-copy evidence: no packaged FTP CSV, valid new empty Store and explicit migrated Store, two fixed-time model scenarios, six page renders, numerical/warm-cache parity, 24 preserved non-cache tables, 1,422 preserved artifacts, integrity OK. These supplied results were not regenerated against personal data in this review. Gate 3 Owner review of the safe running preview remains required, and Gate 4 must verify the real controlled cutover separately.
