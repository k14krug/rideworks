# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-DEV-REVIEW — engineering corrections after independent development review.
**Branch / PR:** `fix/home-dev-review-corrections`; [draft PR #46](https://github.com/k14krug/rideworks/pull/46) targets `dev`.
**State:** `ready_for_review` — Analyst review 5563420406 addressed with reproduced post-Plan/final-response failures and a verified deferred-write correction. Task remains `in_progress` pending Analyst acceptance.

**Corrections:** Home GET carries the existing stress/classification write batches through Plan, Relative Effort, Training State and final response rendering, then flushes just before transaction completion. Matching pending results avoid repeat cold scoring; existing signatures, transaction/retry behavior and default non-Home cache ownership remain intact. Prior tablet/sidebar/readout fixes are retained. No Relative Effort or other model calculation changes.

**Verification:** 529 Python tests pass. Six concurrency cases (classification, post-Plan Relative Effort, final response; cold/invalidated) pass five repeats each; slowest concurrent FTP commit 0.0039s with a 200ms busy timeout. Existing stale-snapshot retry/fresh-FTP checks pass; pending reuse validates signatures and timezone context. Fresh Chromium reruns pass 27,990 assertions across Home, six Activity Details cases and six related routes. All 27 source-mode reviews, 28 table fingerprints, 1,422 originals/modification times and accepted model/evidence/provenance/reference match archived `8f23620`. Six further fixed-clock LA/Tokyo cases and independent dashboard checks pass.

**Remaining:** Full-history Relative Effort scan optimization investigated and deferred (7,236 SQL statements, roughly 0.3–0.4s for 1,420 rides); no new cache/invalidation change. Mixed-source Relative Effort calibration and final visual acceptance remain Owner decisions. Firefox/WebKit, physical devices and screen readers were not tested.

**Evidence:** [Post-Plan follow-up report](reports/HOME-DEV-REVIEW/post-plan-concurrency.md), [initial correction report](reports/HOME-DEV-REVIEW/corrections.md), [Analyst JIT](docs/tasks/HOME-DEV-REVIEW.md). Private captures/logs stay outside Git under `/tmp/rideworks-home-post-plan/` and `/tmp/output/playwright/`. Verification used temporary snapshot servers; existing development processes were not restarted. No production changes or deployment.

**Next action:** Analyst reviews PR #46 and requests the planned independent Astra re-review; Owner retains visual/calibration decisions. Leave PR draft. No merge, production deployment or next-task start authorized.
