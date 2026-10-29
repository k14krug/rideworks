# STATUS.md

**Product:** RideWorks.
**Current task:** RE-02 — Relative Effort UI verification and integration.
**State:** `ready_for_review` — focused integration and local verification complete; awaiting HARD — Analyst review.
**Branch:** `task/re-02-relative-effort`, based on refreshed `main`; `dev` is the feature reference only.
**PR:** [#53 — RE-02 integration](https://github.com/k14krug/rideworks/pull/53) (draft, targeting `main`).
**Owner decision (2026-10-29):** Accept practical mixed-source effort colors; power typically for indoor and HR-estimated stress for outdoor rides. Do not conduct additional calibration research or change `relative-effort-v1`. [Recorded on PR #52](https://github.com/k14krug/rideworks/pull/52).
**Scope:** Verify Home Recent Activities dots, Activities effort column and Activity Review compact card; transplant the minimum compatible changes without disturbing newer accepted Home UI (HOME-UI-02/03) or training calculations. Verify tablet/mobile and Home/FTP concurrency behavior. No broad `dev` merge, production deployment, or Store mutation.
**Last completed task:** HOME-UI-03 was accepted and merged to `main` via [PR #51](https://github.com/k14krug/rideworks/pull/51) on 2026-10-29. It remains accepted and must be preserved.
**Verification:** 534 full-suite tests and 275 synthetic browser assertions passed across seven widths after the Owner's Recent Activities compacting request. [Integration evidence](docs/reviews/2026-10-29-re-02-integration.md).
**Next action:** HARD — Analyst review of the draft PR. HARD — Owner final running-UI acceptance and authorization are required before merging to `main` or deployment.
