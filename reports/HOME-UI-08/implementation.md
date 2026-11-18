# HOME-UI-08 implementation

Home renders from retained data and then makes a separate same-origin request
for a single page of Strava activity summaries. The detector uses the existing
forward window and recognizes Strava IDs already in the API or export records.
It reports an incomplete check when the page fills and no unknown eligible ride
was found. It requests neither details nor streams and writes no activity or
sync checkpoint data. Token refresh uses the existing rotation path if needed.

The server coalesces checks and caches their outcomes for five minutes,
including failures and rate limits. Sync and connection operations invalidate
the result, and an older response cannot replace the new cache. Home submits
to the same protected Sync action as Admin. The existing operation and token
locks, origin validation, and one-use submission nonce apply. Home reports
progress and outcomes, and reloads its current view after completed Sync.

## Verification

- The full suite passed 670 tests using
  `env -u DEBUG .venv/bin/python -m unittest discover -s tests`.
  Coverage includes known export and API IDs, an unknown ride, full pages,
  offline and rate-limit caching, disconnect, overlapping checks, a response
  made stale during Admin Sync, and shared origin, nonce, and busy protections.
- Chromium against a disposable local Dev store used a synthetic Strava client.
  Home content appeared at 57 ms and the new-ride badge at 1,854 ms with a
  deliberately delayed first response. The first load and three reloads used
  one list request in total. During Sync the progress message appeared.
  Home showed the imported synthetic ride, retained its timezone query, and
  cleared the alert after one fresh list check. Home Sync and Admin Sync each
  made one separate list request, for four total across the scenario.
- Checked the Home header and badge at 1440 and 390 px, with no page overflow.
  Admin still redirected to Settings and displayed its sync outcome.
  All upstream responses in this run were controlled. Live Strava behavior
  remains for Owner review in Dev.

[Strava athlete activity list reference](https://developers.strava.com/docs/reference/#api-Activities-getLoggedInAthleteActivities)
