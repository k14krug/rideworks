# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-DEV-REVIEW — engineering corrections after independent development review.
**Branch / PR:** `fix/home-dev-review-corrections`; [draft PR #46](https://github.com/k14krug/rideworks/pull/46) targets `dev`.
**State:** `ready_for_review` — both engineering merge blockers corrected; task remains `in_progress` pending Analyst acceptance.

**Corrections:** Home runs Plan's deferred cache batch before Relative Effort; concurrent FTP edits pass with cold and invalidated caches. Activities uses readable tablet rows. Ride sidebar spacing fits the tested desktop charts, and the conflicting chart-readout rule is removed. No Relative Effort or other model calculation changes.

**Verification:** 524 Python tests pass; both concurrency cases also pass five repetitions each. 28,043 Chromium assertions pass across Home, six Activity Details evidence cases and six related page routes, including tablet/phone, keyboard/touch, exact marker geometry, readout styles and unchanged sidebar-height limits. 27 source-mode reviews, all 28 table fingerprints, all 1,422 original artifacts/modification times, accepted model/evidence/provenance and approved reference match archived `dev`. Six further fixed-clock LA/Tokyo cases preserve ratings, models and dashboard; independent dashboard checks pass.

**Remaining:** Full-history Relative Effort scan optimization investigated and deferred (7,236 SQL statements, roughly 0.3–0.4s for 1,420 rides); no new cache/invalidation change. Mixed-source Relative Effort calibration and final visual acceptance remain Owner decisions. Firefox/WebKit, physical devices and screen readers were not tested.

**Evidence:** [Correction report](reports/HOME-DEV-REVIEW/corrections.md), [Analyst JIT](docs/tasks/HOME-DEV-REVIEW.md). Private captures/logs stay outside Git under `/tmp/rideworks-home-corrections/` and `/tmp/output/playwright/`. Verification used temporary snapshot servers; existing development processes were not restarted. No production changes or deployment.

**Next action:** Analyst reviews PR #46 and requests the planned independent Astra re-review; Owner retains visual/calibration decisions. Leave PR draft. No merge, production deployment or next-task start authorized.
