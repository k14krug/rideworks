# HOME-UI-08 — Check for new Strava rides and sync from Home

## Purpose and Requirements Used
[Product requirements](../PRODUCT_REQUIREMENTS.md); existing Admin Sync and normal forward-looking Strava sync; Owner-approved Home behavior. Use the [Strava API reference](https://developers.strava.com/docs/reference/) for list semantics. HOME-UI-07 is integrated.

## Behavior
- Render Home from local data without waiting for Strava. After load/refresh, check for recent eligible rides separately using the existing connected athlete, safe recent sync window, activity list and known Strava IDs. Count already linked/imported records as known when their Strava ID is established; do not invent a match by title/date. Normal case: one summary request, no details or streams. If a page is full, do not treat an incomplete check as proof of no new rides. Detection does not import, advance checkpoints, or start Sync.
- Reuse the check result per connection/store for about five minutes; coalesce overlapping checks, invalidate after Sync or connection change, and do not let a pre-sync response overwrite newer status. Use a bounded request and avoid repeated calls on failure or rate limit. No timer polling or webhook.
- Show “New rides on Strava” when found. Distinguish failed/incomplete checks and no connection from no new rides in the checked window. No exact count or claim about all history. Never block Home if Strava is down.
- Provide Sync now on Home whenever the existing connection permits it, even with no alert. Reuse Admin's authenticated, CSRF-protected sync workflow, not a second import path. Prevent overlapping Home/Admin runs. Keep the user on Home, show running and final outcomes, refresh Home data after committed ride imports, and recheck or update the indicator without masking failures. Keep Admin behavior and current data processing intact. Segment work is not part of this task.

## Verification and outputs
Tests for known vs new IDs, check cache/coalescing, incomplete list, offline/rate-limit and disconnected paths, stale response after Sync, existing protections, and overlapping runs. In running Dev verify Home loads while the check is delayed; measure Home render and badge latency separately, report request count on repeated reloads, and verify a new ride triggers the alert and Sync from Home updates the dashboard and clears the alert after confirmation. Use synthetic/controlled responses when a real unsynced ride is unavailable and identify which evidence is which. Check desktop and narrow viewport and Admin regression. Draft PR and sanitized implementation report; no credentials, private IDs or ride data in Git.

## Execution Control
**Allowed Invocation: `/TASK only`.** Start from refreshed main, one active task. Stop at HARD — Analyst, then HARD — Owner in Dev. Stop if preserving the existing sync protections would require a broader redesign. No merge or production deployment authorized.
