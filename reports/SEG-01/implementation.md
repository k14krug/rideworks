# SEG-01 Zwift-first implementation

Segments saves an exact Owner-selected effort from authenticated Strava
activity detail. The activity and effort must belong to the connected athlete,
the ride must have Zwift source evidence, and the effort supplies its own
segment ID, elapsed time, and date. SQLite stores exact IDs as text and saves
only the required effort fields. Re-adding an effort preserves a single
attempt. Separate attempts on the same ride remain separate rows.

Both page counts use exact, unique associations across established Strava API
and export IDs. The association is calculated from saved data so an unmatched
effort becomes linked when its ride is established. A filtered Segments page
shows the saved attempts for one ride. The unfiltered page shows dated history
and fastest saved effort.

Home and Admin share the existing manual Sync route. A first forward Strava
observation without an established Strava link queues a ride if the watchlist
is populated and its summary has VirtualRide classification and a Zwift
upload reference. A ride already filed locally can qualify when that Sync
establishes its first Strava link. Existing API and export-linked rides do not
get checked from overlap. Sync currently fetches only summary and stream
evidence, so there is no complete activity detail to reuse from those steps.

Import, checkpoint and queue entries commit together. Each Sync checks up to
five pending rides, including on a Sync with no new activities. A validated
complete detail with zero watched efforts clears the queue entry. Failures and
deferred work remain pending. Rate and authorization failures stop additional
segment requests for that run. Detailed follow-up failures are reported
separately from the already committed ride imports.

## Verification

- Full Python suite passed 677 tests with `env -u DEBUG .venv/bin/python -m
  unittest discover -s tests`. The five focused SEG-01 tests also passed.
- Controlled integration tests exercise 64-bit identifiers, trusted link
  input, ownership and ride validation, CSRF and the shared operation lock,
  deduplication, separate attempts, unmatched and later-linked efforts,
  and offline views. They cover an empty watchlist, bounded deferral, rate
  and authorization failures, incomplete responses, successful zero-match
  checks, and retry during Sync without new rides.
- Chromium at 1440 and 390 px used a disposable Dev store and controlled
  Strava responses. It saved two attempts, linked them after Home imported
  their ride, displayed a rate-limit partial result, and cleared pending work
  on Admin Sync. Both Home and Activities linked to filtered history. The
  filter displayed both attempts and a link back to the watchlist. No page
  overflow in the checked views.
- Two bounded live read-only activity-detail calls checked the implementation
  contract on the earlier and later reference rides. Both exact attempts
  passed validation and both responses identified Zwift. Live forward capture
  awaits an eligible newly synced ride in Owner Dev review. No live probe
  responses or identifiers were kept in repository artifacts.

The saved history follows the Owner's approved durable scope. Strava's current
API terms restrict persistence and limit transient caching to seven days.
See [Strava API Policy](https://www.strava.com/legal/api_policy) and the
[sanitized first probe](probe.md).
