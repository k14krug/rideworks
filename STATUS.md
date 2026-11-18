# STATUS.md

**Product:** RideWorks.
**Current task:** SEG-01 — Saved watched Strava segments and Sync updates.
**State:** `blocked` for implementation — Analyst accepted per-ride Zwift evidence; original historical-import gate not cleared.
**Branch:** `seg-01-watched-segments`.
**Verification:** Activity detail verified exact efforts and unique local ride links on both reference rides. Historical coverage and routine Sync behavior remain unverified. See [sanitized probe report](reports/SEG-01/probe.md).
**Next action:** No further probe or Dex invocation pending. Analyst recommends a Zwift-first release: add a watched segment and save selected older efforts by activity-effort link; capture matching efforts from newly synced Zwift rides through the shared Home/Admin Sync, with bounded retries for failed lookups. Keep saved history and ride links; label fastest saved effort and make no claim of complete history. No automatic historical backfill. This is a proposed scope change, not implementation authorization. After explicit Owner approval of the narrower release, Analyst must revise the JIT before `/TASK SEG-01`. No merge or deployment.
