# RideWorks

## Everyday startup and private data

Open the **RideWorks** desktop shortcut, or open the executable `start-rideworks`
in the checkout. It starts the existing loopback server and opens
`http://127.0.0.1:8766/`; reopening the launcher uses the already-running store.
No Python command, store selection or framework setup is needed for daily use.

The default store is **top-level `data/` beside `pyproject.toml`**, independent
of the working directory. Settings shows the active data folder. This is distinct
from packaged `rideworks/data/` reference resources. A missing established store
stops startup with a restore/select-store message; it never opens a blank history.
For a genuinely new installation, an explicit `import-fit`/`import-strava-export`
command creates a store. Tests use explicit temporary/disposable directories.
CLI and environment data-directory overrides remain available for those cases.

Include the entire production `data/` folder in the Owner's existing backup system:
`rideworks.sqlite3`, `originals/`, `.strava-tokens.json`, `.strava-settings.json`,
and the approved reference resources. Historical FTP now resides in SQLite; see the FTP-01 promotion notes below. Include any SQLite `-wal`/`-shm`
sidecars if present, and take a consistent database snapshot or stop the app for
file-based backups. Protect the ignored checkout `.env` separately for app
credentials. `rideworks.log` and `.staging` are transient; `.strava.lock` is a
runtime lock, not a credential. No new scheduled backup system is provided.

During OPS-01 acceptance the unchanged `local_data/p2-05-review` source remains
rollback: stop the new app and explicitly launch that source if needed. Remove
it only after Owner acceptance of the new everyday store. Old research instructions
below describe historical phases; their task-specific store paths are not daily
launch instructions.

P1-01 uses Python 3.10+, standard-library SQLite, and `fitdecode==0.11.0`.
It runs independently of the retired Strava application and its dependencies.
From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m rideworks import-fit /path/to/activity.fit.gz
.venv/bin/python -m rideworks inspect <activity-id>
.venv/bin/python -m rideworks reextract <source-id>
```

The installed `rideworks` command provides the same interface. Place the optional
`--data-dir /path/to/private-data` before the subcommand. Directory precedence is
explicit argument, `RIDEWORKS_DATA_DIR`, then project-root `data/`. Relative explicit
paths resolve at invocation; the default is independent of the working directory.
Originals and the SQLite database are private runtime data; keep them out of Git.

A successful import returns independently generated Activity and Source UUIDs
and the current extraction UUID. Reimporting identical received bytes verifies
the established original and returns those same identities. Different bytes,
including different gzip packaging, create a separate Activity in this phase.
Filename suffixes do not establish packaging or FIT validity. Original basenames
are retained for inspection; external paths are not persisted.

`Store(data_dir)` is a context manager. `import_fit(path)` and
`reextract(source_id)` return identity/status dictionaries. `get_activity(id)`
returns `activity` metadata and a `sources` list; `get_source(id)` returns one
Source snapshot containing `source`, `extraction`, `summary`, `records`, `laps`,
`events`, and `availability`. These methods use a consistent database read
transaction. `inspect(id)` omits records and detailed lap/event rows.

The physical tables have typed columns, with each normalized row linked to its
extraction and thus to its Source. Activity contains identity and creation time
only. Multiple Sources can reference an Activity; association/reconciliation
of different artifacts is deferred. Source owns one current extraction. A
successful re-extraction replaces that extraction transactionally and changes
its UUID, allowing later calculations to detect stale inputs. Old extraction
snapshots are not retained in P1-01.

Records preserve `record_index` (zero-based record ordinal) and `source_order`
(zero-based decoder frame ordinal, including headers and definitions). Retrieve
in record order, retaining duplicates, backward times, gaps and nulls. Timestamps
are ISO 8601 UTC strings; missing timestamps are null. Device-relative timestamps
are rejected instead of guessed into calendar time. Source summary units are
seconds, metres, watts, bpm and rpm as specified by `SUMMARY_UNITS`.
Elapsed and timer time remain separate. The decoder's default processor supplies
UTC date-time decoding and FIT source units; the presentation-unit processor is
not used. See the upstream [processor source](https://github.com/polyvertex/fitdecode/blob/master/fitdecode/processors.py).

Power/HR availability includes total, present and missing counts, with statuses
`present`, `present_with_missing` or `observed_absent`. Origin is independently
`unknown`; field presence does not prove measurement. Other record signals are
not extracted, and remain recoverable from the original. No application analysis
metrics are calculated here.

Import copies received bytes to managed staging, hashes and parses that copy,
and places exact bytes under `originals/<sha256>.fit[.gz]` using exclusive file
creation. Files and directory entries are synchronized before the database
transaction commits. Mutations serialize with a SQLite write transaction.
Failed imports roll back all metadata and safely remove newly created
unreferenced originals. A crash may leave an unreferenced original/staging file;
an identical original is reused only after integrity verification. Established
originals are never silently overwritten or repaired. Re-extraction verifies
stored integrity before decoding and leaves the prior current extraction intact
on decoder or database failure.

Only one FIT file with one activity session and exactly one `file_id` whose type
is `activity` is supported. Missing/duplicate `file_id` messages, chained FIT
files, multiple sessions, non-activity file types, malformed gzip/FIT, and invalid
CRCs fail clearly. Exact originals enable later extraction of fields omitted here.

Verification:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tools/verify_rideworks_import.py --input "$P1_01_INPUT" --work-dir /tmp
```

Set `P1_01_INPUT` to the local-only representative `21538875902.fit.gz`. The
acceptance utility uses and removes a disposable copy and disposable store,
runs CLI commands from a different working directory, and emits only compact
facts. It never modifies the supplied file. Run with assertions enabled.

P1-02 adds on-demand activity analysis:

```bash
.venv/bin/python -m rideworks analyze <activity-id>
.venv/bin/python tools/verify_rideworks_analysis.py --input "$P1_01_INPUT" --work-dir /tmp
```

`rideworks.analysis.analyze_activity(store, activity_id)` consumes the P1-01
read boundary and returns `activity`, `source`, `extraction`, `source_summary`,
`native_records`, `availability`, and `best_20_minute_power`. The summary's
`values` remain source-supplied FIT session evidence; the best-20 result is
explicitly `calculated` and identifies its Activity, Source and extraction.
The native record dictionaries, including order, timestamps, zero and null
values, pass through unchanged. The normal `analyze` CLI omits those records.

Method `best-average-power-v1` evaluates exactly 1,200 consecutive records with
complete power and exact one-second timestamp deltas. Each candidate represents
`[start, start + 1200 seconds)` and requires no additional endpoint sample.
Zero watts contribute to the mean. Missing power and timing defects disqualify
only the windows containing/spanning them. Equal unrounded means select the
earliest source-record window. The result includes unrounded watts, nearest
whole watts with .5 upward rounding, selected indices/times and eligibility.
No eligible window returns `unavailable` with a reason and null result values.
Unexpected power values fail clearly for investigation rather than being repaired.

The Phase 1 single-Activity analysis remains on demand. Each call reads the
current extraction and recalculates. Multiple candidate FIT Sources fail with
an explicit selection-decision error; no source-ranking policy is introduced.
`tools/verify_rideworks_analysis.py` independently enumerates complete windows,
directly sums their samples, and applies Decimal half-up rounding. It compares
its result against the application, checks source/native evidence unchanged,
and verifies analysis after re-extraction using a disposable store/input copy.
Run verification with assertions enabled.

## Local browser review (P1-03)

Import once, then start the server with that same private data directory:

```bash
.venv/bin/python -m rideworks --data-dir local_data/p1-03-review import-fit local_data/p1-01-input/21538875902.fit.gz
.venv/bin/python -m rideworks --data-dir local_data/p1-03-review serve --port 8765
```

Open the printed URL, normally `http://127.0.0.1:8765/`, and select a ride in
Activities. The stable review URL is `/activities/<activity-id>`. Stop with
Ctrl+C and run the same server command to reopen the activity without importing
again. Use `serve --port 8767` to choose a different local port. The server binds
only to `127.0.0.1`; for the current private LAN deployment, see the nginx section
below. There is no account or upload workflow.

The browser application uses Python's standard-library HTTP server, server-rendered
HTML and packaged local CSS/JavaScript/SVG. No retired application imports,
new runtime dependencies, frontend build step, CDN or external runtime requests
are required. `Store.list_activities()` lists activities with exactly one current
FIT Source/session; it does not choose among ambiguous Sources.

Normal review uses miles, feet, W, bpm and rpm; original source SI values remain
unchanged. Dates use the browser's local timezone with a visible offset (labeled
source UTC fallback without JavaScript). FIT elapsed and timer durations are
distinct. The best-20 panel consumes the accepted `analyze_activity` result and
labels it RideWorks-calculated, separately from FIT session summaries.

The chart receives native record indices, UTC timestamps, power and HR unchanged
in native order. Elapsed time is a display transformation relative to the source
session start (first available native timestamp if start is absent). Zero remains
a sample; missing values/timestamps break paths, as do forward gaps greater than
one second and backward jumps. Records without timestamps remain inspectable
with arrow keys rather than being assigned invented times. Pointer inspection
chooses the nearest timestamped native sample, with the first native record
winning an equal-distance tie. Focus the chart and use arrow keys, Home or End
to inspect every record, including duplicate timestamps. Each signal has its
own labeled axis. No resampling, smoothing or analytical recalculation occurs
in the browser.

Source and calculation details expose identities, artifact integrity, versions,
availability and unknown sensor origins without private paths or coordinates.
The local SVG mark follows the verified compact brand board; Owner approval of
the applied identity and screen is required before Phase 1 acceptance. See
`reports/P1-03/verification.md` for the review procedure and evidence.

## Optional repository .env startup configuration

From the repository root, optionally copy the safe `.env.example` to `.env` and
edit its local values. `.env` remains Git-ignored; do not commit its contents.
The CLI finds this file next to the checkout's `pyproject.toml`, independently
of the launch directory. Installed wheels without a checkout do not look for
`.env`; exported environment variables and CLI flags still work.

| Setting | Precedence / default | Meaning |
| --- | --- | --- |
| Data directory | `--data-dir` > exported `RIDEWORKS_DATA_DIR` > repository `.env` > project-root `data/` | Applies to all CLI commands. Original/source data stays private. |
| Server port | `serve --port` > exported `RUN_PORT` > repository `.env` > `8766` | Decimal integer 1–65535; always binds to `127.0.0.1`. |
| Request diagnostics | exported `DEBUG` > repository `.env` > off | Accepts 0/1, false/true, no/yes or off/on, case-insensitively. |
| Browser-facing origin | exported `PUBLIC_ORIGIN` > repository `.env` > local access only | HTTP or HTTPS scheme, hostname/IP and optional external port; no path, trailing slash, query, fragment or userinfo. |

`DEBUG` enables only server-console request method, status and response timing.
Errors report the exception class without private
paths, query strings, credentials or tracebacks in the browser. There is **no
interactive debugger or automatic reloader**; restart the server to pick up Python
changes. The former Flask-named port/debug keys are ignored; update your process
environment or `.env` to `RUN_PORT` and `DEBUG`.

Only these four startup keys are read. Exported variables are not overwritten and the
process environment is not mutated. The small file reader accepts `KEY=value`,
optional `export `, single/double quotes, blank lines and `#` comments. Quote
values with spaces or literal `#`. There is no shell execution, interpolation,
variable expansion or multiline syntax. Unrelated legacy settings are ignored.
The last file assignment wins. Selected invalid port/debug/origin values fail before
the server binds; higher-priority CLI/exported values bypass overridden file
values. An empty data directory is rejected rather than treated as the checkout.
Relative data-directory paths retain the existing resolution at invocation.

The explicit review command above remains deterministic even if `.env` selects
another data directory or port. With the example values, this shorthand also works:

```bash
.venv/bin/python -m rideworks serve
```

## Private home-LAN nginx deployment (HTTP)

The Owner's production deployment uses HTTP on a trusted home network. HTTPS
and TLS configuration are not required. Keep nginx and RideWorks on the same
host; the Python backend continues listening only on `127.0.0.1`.

Set the browser's actual origin in your private environment file, for example:

```dotenv
RUN_PORT=8766
DEBUG=0
PUBLIC_ORIGIN=http://rideworks.lan
```

`rideworks.lan` is illustrative: use your actual LAN hostname or IP. If the
browser uses `http://192.168.1.20:8080`, set exactly that origin instead.
HTTPS also works if independently configured, but is optional. DNS names are
case-normalized; explicit default ports (`:80` for HTTP, `:443` for HTTPS) are
omitted from the normalized origin. IPv6 literals must use brackets. Empty or
malformed origins fail startup. Omit `PUBLIC_ORIGIN` for the original local-only
behavior. Only the configured public origin and existing local origins can
submit forms, and each action still requires its valid nonce.

In your existing nginx `server` block, forward the browser-visible Host and
leave the browser's Origin unchanged:

```nginx
listen 80;
server_name rideworks.lan;

location / {
    proxy_pass http://127.0.0.1:8766;
    proxy_set_header Host $http_host;
}
```

Use the selected `RUN_PORT` in `proxy_pass`. `$http_host` preserves an external
port such as `:8080`; that port belongs in `PUBLIC_ORIGIN` and need not equal
the backend port. The [nginx proxy documentation](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)
describes Host forwarding. RideWorks checks Host against local addresses or the
configured public host/port; default external ports may be explicit or omitted.
Other or duplicate Host/Origin headers are rejected. `X-Forwarded-Host` and
`X-Forwarded-Proto` do not grant access or change OAuth URLs. No Origin rewriting
is necessary.

For an existing systemd service, a service section can use:

```ini
[Service]
WorkingDirectory=/srv/rideworks
EnvironmentFile=/srv/rideworks/.env
ExecStart=/srv/rideworks/.venv/bin/python -m rideworks serve
```

Adjust the paths for your installation. systemd loads `EnvironmentFile` entries
into the process environment, which takes precedence over the repository file.
See systemd's [environment file documentation](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml).
Keep `--port` out of `ExecStart` so `RUN_PORT` applies; do not put shell variable
expansion in the executable path. Restart the service after changing settings.
The desktop `start-rideworks` launcher still explicitly uses port **8766**.

Existing Strava tokens remain connected; configuring the origin does not force
reauthorization. Browser Connect uses `<PUBLIC_ORIGIN>/strava/callback` when
configured, otherwise the existing loopback callback. Set Strava's Authorization
Callback Domain to the selected hostname/IP (host only), **if Strava accepts
it**. [Strava's authentication documentation](https://developers.strava.com/docs/authentication/)
requires redirect URI domain agreement and explicitly permits localhost and
127.0.0.1; it does not confirm support for every private LAN hostname/IP. A real
provider rejection needs a separate callback-domain diagnosis, not a TLS change
or bypass. CLI `strava-connect` continues using its loopback callback. Local
tests use fake Strava responses and cannot establish provider acceptance of
your private domain.

## Current activity titles and future source-title finding

Phase 1 has no actual source activity-name field. Both Activities and review
therefore show an explicitly **Derived title**: type label plus the FIT source
start date in UTC, using fixed English month names (for example
`Virtual Ride — Sep 29, 2026`). This does not depend on today's date, browser
locale/timezone or import time. Missing date remains `date unavailable`; no
calendar value is manufactured. Cycling type and Virtual Activity subtype stay
separate. Title origin/basis are inspectable in Source details.

The Owner correction records a future durable-history requirement: preserve and
prefer an actual source activity title when available, with provenance (for
example Strava export/API `Activity Name`), while retaining type/subtype separately.
This task adds no source-title persistence/reconciliation, API/export enrichment
or naming policy beyond the explicitly derived FIT-only fallback.

## Historical Strava-export import (P2-01)

Import the original export ZIP in one command, or supply an extracted export
root containing exactly one `activities.csv`:

```bash
.venv/bin/python -m rideworks --data-dir <data-dir> import-strava-export <export.zip-or-root>
```

The command emits a compact JSON report with row, creation, enrichment, reuse,
CSV-only, artifact, format and failure counts. A partial import exits with status
1 and keeps independent successful activities. Fix the reported row/file problem
and rerun the same command; established IDs and equivalent evidence are reused.
Row indexes are **1-based data-row positions**, excluding the CSV header. Reports
use these indexes and fixed failure categories, rather than private title/path
or parser-error text. `inspect <activity-id>` exposes locally retained evidence.

The ZIP is read directly, without extracting it. Only exact `activities.csv`
bytes and explicitly referenced activity artifacts are preserved; photos,
account details, routes and other unrelated export contents are not imported.
Unsafe references, symlinks, duplicate/ambiguous ZIP members, malformed-width CSV
rows and duplicate activity IDs/file references are rejected before evidence is
written. A structurally valid export with an unreadable or malformed individual
activity file keeps that row's CSV source and reports the file failure. It does
not create a successful file Source/extraction for the failed file.

Opening an accepted data directory applies additive migrations through schema 4.
This is an additive SQLite migration: existing tables, Activity/Source IDs,
artifacts and FIT extractions remain intact. A failed migration rolls back its
DDL/version changes; it does not make a partially migrated store appear usable.
Keep your usual local backup; the importer does not replace the existing store.

Evidence remains source-centered:

- The exact CSV is preserved once per byte identity. Each row Source records its
  Strava external ID, actual title, separate type/sport-type/date/reference,
  mapping version and links to its row in that snapshot.
- Structured CSV extraction is an allowlist of useful identity/title/type/date
  and distance/duration/elevation/power/HR/cadence fields. Description, private
  notes and other arbitrary text are not normalized. The preserved CSV remains
  the recovery path for omitted fields.
- Repeated summary columns retain their original positions, raw values,
  parsed numbers, missing/unparsed status and source units. Distance, duration
  and elevation CSV units are explicitly unspecified where the export labels
  do not establish them. No global km/metre or timer/moving-time equivalence is
  guessed. CSV dates without offsets retain unknown timezone.
- FIT decoding uses the accepted `fitdecode==0.11.0` / `fit-v2` path. TCX/GPX use
  standard-library ElementTree / `xml-activity-v1`. Received gzip bytes remain
  the original; decompression and leading XML whitespace removal are transient.
- XML preserves point order, zero/missing power/HR, absent timestamps, duplicate
  timestamps, backward jumps, gaps, fractional seconds and offset-unknown times.
  Track segment boundaries are retained as record indexes in `xml_context`.
- TCX lap timing/distance/power/HR summaries remain explicitly named lap source
  fields in `xml_context.lap_summaries`; they are not relabeled as FIT elapsed or
  timer time or silently aggregated into an Activity-wide summary.
- Garmin qualified TCX Watts and GPX HR fields are mapped. The observed GPX
  unqualified/core `power` and legacy `{TrackPointExtension}hr` dialect is also
  mapped as source evidence with unknown origin. Private/unknown GPX summary
  extensions are left in the original; summary watts never become point power.
- CSV-only activities have a normal Activity and row Source. Native records are
  unavailable (`records=None`), rather than an observed empty/absent stream.

Exact established artifact identity plus its explicit CSV relationship, or an
already-associated Strava ID, can enrich an existing Activity. Conflicting
established identities are left unresolved. There is no fuzzy time/name/distance
matcher: pre-existing local Activities still lacking an established export
relationship are reported as unresolved, without guessing which row matches.
The representative accepted Phase 1 FIT therefore keeps its Activity/Source/
extraction IDs and gains separately attributable actual title evidence.

Changed recognized row evidence creates a new row Source on the established
Activity. Changed file bytes create separately preserved file evidence. Changed
CSV bytes always preserve a new exact snapshot; equivalent recognized evidence
can reuse its row Source while gaining a link to the new snapshot. Earlier
source evidence is never overwritten.

`Store.activity_history()` exposes **all** Activities, source titles/provenance,
type/date/summary/missingness, kinds/formats, native-power availability and
source/extraction identity, without loading raw record arrays or selecting one
universal canonical source. `get_activity()` / `get_source()` expose detailed
per-source evidence. This is the read boundary for later Phase 2 tasks; the
accepted Phase 1 browser and derived title presentation remain their current
bounded behavior until P2-02. This task adds no historical trend or API sync.

Reproduce the disposable, seeded acceptance against the known export:

```bash
.venv/bin/python tools/verify_rideworks_export.py \
  --export <local-export.zip-or-root> --work-dir <local-work-directory>
```

This verifier checks the known 1,434/1,421/13 population before import, seeds the
accepted representative artifact, invokes the product bulk command, compares
**all** preserved originals against received bytes/hash/size, checks enrichment,
reads FIT/TCX/GPX/CSV-only examples through Store, then reruns in another process
and checks every persisted identity/current extraction and the full read result.
It removes its disposable store and prints aggregate evidence only. Neither the
personal export, runtime database, source titles nor raw streams belong in Git.


P2-01 JIT §16A authorizes one FIT timing exception: an integer-valued
`lap.timestamp` is retained exactly in `fit_lap_timestamps`, tied to its
extraction/lap source order and `timestamp` field. Its status is
`present_uninterpreted_non_absolute`, and its absolute lap timestamp stays null.
No timebase, replacement UTC instant or device-relative interpretation is inferred.
Aware lap timestamps retain the accepted UTC normalization. Record, session,
event and lap-start timing keep their existing strict handling.

Schema 3 adds only this typed FIT table; schema-1 and schema-2 migration preserves
all previous evidence and extraction versions. New FIT extraction uses `fit-v2`
so the widened lap representation is identifiable. Existing `fit-v1` extraction
is not silently rewritten; explicit `reextract` from the preserved original
creates a current `fit-v2` revision and reproduces raw lap integers exactly.
`get_source()`, `get_activity()` and compact `inspect` expose this evidence.

FIT conflict checks apply to the understood extraction fields; disagreement in
unused native/enhanced speed fields does not reject the source. Those fields
remain recoverable from its exact original. XML timestamps with 1–6 fractional
decimal places are parsed exactly, including centiseconds on Python 3.10.
Greater precision is rejected rather than silently truncated. Missing offsets
remain unknown; no sample is resampled or moved to a different instant.

### Activities browser

Start the same loopback-only server against your imported store:

```bash
python -m rideworks --data-dir <data-dir> serve --port 8765
```

Open `http://127.0.0.1:8765/activities`. Activities defaults to cycling, newest first,
with 30 rows per page. Select All activities to include non-cycling history;
individual source type/subtype choices, partial case-insensitive title search,
From/To dates and newest/oldest/longest-duration/longest-distance sorts use GET
query state. Applying filters returns to page 1; previous/next retain them.
Missing sort values come last and remain unavailable, including distances or
durations whose CSV units have not been established. Date has its own column,
separate from Title. Known absolute instants display on one line in your browser's
local timezone, without a timezone suffix. From/To matches that same displayed local calendar day, including
historical daylight-saving rules. Dates without an offset retain their supplied
calendar day and explicit unknown timezone.

JavaScript establishes the browser timezone in GET state (`tz`) and keeps it in
filter submissions/pagination. This is presentation context only: source times
and provenance are never rewritten. Without a supported browser timezone,
absolute instants do not enter a date-filter match under a guessed timezone;
the page explains that local filtering needs JavaScript. Unknown-zone source
dates can still filter by their supplied day.

Display prefers the latest non-empty imported Strava-export title without
changing any source observation. Type/subtype remain separate. Without a source
name, the browser labels its type/date fallback as derived. Hover over list
distance/duration to see the selected file summary context. This narrow display
policy lives in `rideworks/history.py`; it is not a universal source ranking.

Every row opens its stable `/activities/<Activity ID>` route. A single supported
FIT source keeps the accepted chart and best-20 review, now with source-title
provenance. TCX, GPX, CSV-only and ambiguous FIT evidence get a thin review of
their associated source metadata/availability, with detailed analysis explicitly
unavailable. CSV summary watts are never substituted for native streams.

For the known imported history, local HTTP/restart acceptance is reproducible:

```bash
python tools/verify_rideworks_browser.py --data-dir <local-review-store> \
  --representative <local-representative.fit.gz>
```

This starts two successive loopback verification servers on port 8767 (override
with `--port`), checks the full known population/query/routes/restart and emits
aggregate JSON. It leaves the store intact. Real-browser inspection and Owner
visual/usability approval remain separate required P2-02 gates.

### P2-02 full-history Owner review

The prepared review store is `local_data/p2-02-review`. Use its dedicated
**port 8766** instance:

```bash
.venv/bin/python -m rideworks --data-dir local_data/p2-02-review serve --port 8766
```

Open **http://127.0.0.1:8766/**. The normal page reports **1,410 cycling Activities /
1,434 in history**; All activities reports 1,434 matching Activities. If this
server is already running, open its URL directly. An older Phase 1 process on
port 8765 may point to the separate one-activity store; that is not the P2-02
full-history review instance. Use the port and counts above to identify the
correct store before reviewing the browser.

## Performance history

Normal Sync now automatically brings Performance current when evidence or policy is pending. The explicit rebuild remains a maintenance/recovery command; open `/performance` for the current history:

```bash
.venv/bin/python -m rideworks --data-dir '<data-dir>' rebuild-performance
.venv/bin/python -m rideworks --data-dir '<data-dir>' serve --port 8768
```

The rebuild emits aggregate counts only. Current policy `virtual-power-evidence-v2` uses
the latest non-empty Strava activity-type observation, or unambiguous native
virtual-session evidence when that observation is absent. Outdoor Ride and
non-virtual Activities are excluded before reading native streams. Each FIT,
TCX or GPX candidate is evaluated with unchanged `best-average-power-v1` rules.
Exactly one eligible native Source is required; multiple eligible Sources are
excluded rather than ranked. Native Virtual Ride power is accepted for this
history, without claiming measured provenance. The earlier file-only policy `virtual-native-power-v1` remains historical evidence. CSV/session/lap summaries do not
substitute for native power. Naive native timestamps are not guessed into UTC. File-backed power controls even when ineligible; API streams cannot rescue its result. With no retained file-backed power, a current API summary/stream pair may qualify for Virtual Ride when device watts are confirmed, time/watts are high resolution and full length, integer offsets increase strictly, and a complete one-second window exists.

Schema 4 adds a specific `performance_history` table keyed by Activity, duration
and policy, retaining method, source/extraction identities, classification context,
raw/display watts, window context and rebuild time. API results keep native source/extraction columns null and retain stream/summary IDs, digest/mapping, device watts, returned offsets, and method/policy in result JSON and freshness signatures. API samples never enter native records. Historical v1 rows remain available while current pages select v2 only.
The entire rebuild uses one transaction; fatal corruption leaves the previously
committed history intact. Re-extraction removes affected eligible results through
their foreign key, and metadata/input identity checks hide changed classifications
or competing sources until a rebuild. No background recalculation is added.

Performance is one analysis surface, rendering persisted results and metadata
without querying native streams. Range offers 3 months, 6 months, 1 year, 3 years
and All. View offers Rolling 42-day (default), Monthly best and Yearly best.
The default range is one year. Optional subdued ride dots remain supporting
observations. Four compact cards show current 42-day best, latest eligible ride,
best in the last 12 months and lifetime best, with Activity date/link and freshness.
All eligible results remain inspectable in 30-row evidence pages. A collapsed
Future Performance candidates section labels possible later direction explicitly;
it does not implement or commit to those capabilities.

The rolling line is the highest raw result in `(t - 42 days, t]`; exact ties
retain the earliest Activity. Entry and exact 42-day expiry cause discrete changes;
periods without qualifying evidence have gaps. It does not estimate daily fitness.
Ranges and summaries end at the page's as-of UTC instant, with calendar-month
cutoffs clamped at month ends. Monthly/yearly bests group the displayed local
calendar month/year and use only rides inside the selected range. One best is
shown per non-empty period, at its contributing ride date. Monthly/yearly views
use lines with point markers; lines connect only consecutive calendar periods.
Missing months/years have no mark and break the line. The same raw-max/earliest-tie rule applies, without averaging or smoothing.
Unknown-zone source dates remain explicitly source-dated in period views and
lifetime evidence, without membership in absolute timed windows.

Hover, arrow keys, Home/End and Enter inspect or open the contributing Activity.
Known date/time readouts are browser-local, compact and omit GMT offset suffixes;
unknown-zone source days stay explicit. Missing dates are reported and not invented.
Eligibility/method and selected-source provenance are inspectable in details.

Reproducible verification commands, using a disposable full-history copy:

```bash
.venv/bin/python tools/verify_rideworks_performance.py \
  --data-dir '<data-dir>' --representative '<representative.fit.gz>'
.venv/bin/python tools/verify_rideworks_performance_http.py \
  --data-dir '<data-dir>' --representative '<representative.fit.gz>'
.venv/bin/python tools/verify_rideworks_performance_ui.py \
  --data-dir '<data-dir>' --port 8768 --session rideworks-p2-03
```

The independent verifier segments complete timing/power runs and enumerates
windows with prefix sums and Decimal rounding, independently of the production
rolling-sum function. It checks the entire population and all eligible results,
classification/source identities, rebuild idempotence, restart and SQLite integrity.
A direct scan independently checks rolling winners at every entry/expiry event
and all four summary contexts on the full eligible history.
HTTP verification includes accepted Activities/rich/thin review regressions and
two Performance server processes. UI verification needs an existing managed
Chromium Playwright CLI session and the server; it writes ignored local screenshots
and emits aggregate JSON. Monthly/yearly winners are checked against independent
calendar grouping at every range, in two browser timezones, with synthetic
raw/tie/zero, month/year-boundary and partial-range cases. No private titles or IDs are emitted by these tools.

The prepared P2-03 Owner review copy is `local_data/p2-03-review`:

```bash
.venv/bin/python -m rideworks --data-dir local_data/p2-03-review serve --port 8768
```

Open **http://127.0.0.1:8768/performance** for P2-03 review. This copy contains
1,434 Activities and 1,022 current eligible points. The accepted P2-02 store and
older review servers are separate instances.


## Prior six-week context in Activity Review (P2-04)

Rich Activity Review adds a distinct **Compared with previous 6 weeks** inset
inside Best 20-minute power: prominent This ride and Prior 42-day best values,
a neutral watt difference, compact prior date/title, Open prior ride and View
Performance. The visible difference subtracts the displayed whole-watt values,
so 120 W versus 195 W shows 75 W below; equal values show Same displayed watts.
Raw averages still choose the prior result and remain inspectable in details.
No difference is fabricated without a baseline.
Values stay neutral; no fitness interpretation is added. Collapsed Comparison
details retain raw values, selected input
identities, method/policy/duration, exact bounds and current-Activity exclusion.

Selection reads current persisted P2-03 results and metadata. For absolute
Activity start `t`, the interval is exactly `(t - 42 days, t)`; both endpoints
are excluded. Highest raw watts win, with earliest Activity start then stable
Activity ID resolving exact ties. Unknown-zone prior dates do not enter the
exact timed window. Missing/stale/ineligible current results show an explicit
unavailable reason; an empty prior window stays unavailable. No summary watts,
older period bests or zeros substitute. Ordinary FIT analysis remains separate.
Thin reviews retain their evidence-appropriate behavior.

There is no comparison table, archive import or source re-extraction. Normal Sync now handles pending Performance through the shared automatic convergence step; viewing a page never rebuilds it. Baseline selection scans no native records; the existing
current-ride chart/calculation still reads that ride's native evidence normally.

Verification uses a disposable copy of accepted P2-03 history, preserving the
accepted store and originals. Run the independent checker first; it writes
ignored local review links used by the HTTP/browser checkers:

```bash
.venv/bin/python tools/verify_rideworks_recent_context.py \
  --data-dir '<accepted-store-copy>' --representative '<representative.fit.gz>'
.venv/bin/python tools/verify_rideworks_recent_context_http.py \
  --data-dir '<accepted-store-copy>' --representative '<representative.fit.gz>'
.venv/bin/python tools/verify_rideworks_recent_context_ui.py \
  --port 8769 --session rideworks-p2-04
```

The final command requires a running review server and managed Playwright CLI
Chromium session. Review copy startup:

```bash
.venv/bin/python -m rideworks --data-dir local_data/p2-04-review serve --port 8769
```

Private Activity URLs are in `output/playwright/p2-04-review-links.json`;
`representative`, `no_prior` and `outdoor` select useful Owner review cases.

## Manual Strava synchronization (P2-05)

From the repository root, create your local configuration from the safe example:

```bash
cp -n .env.example .env
```

Open the ignored `.env` and fill in `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`
using your application's Client ID and Client Secret from
[Strava API settings](https://www.strava.com/settings/api). If `.env` already
exists, the command preserves it; add/update the two entries there while keeping
your other settings. Exported environment variables still override `.env`.
Keep credential values and tokens local.

For local review with `PUBLIC_ORIGIN` omitted, in Strava's **Authorization Callback
Domain** field enter **`127.0.0.1`**
(host only, without a scheme, port or path). RideWorks supplies the full redirect
URI **`http://127.0.0.1:8771/strava/callback`** for the review app below. The web
callback uses the running app's port in this local mode; no second callback server
is needed. With `PUBLIC_ORIGIN` set, browser Connect uses that configured origin
instead; see the nginx deployment section for callback-domain requirements.
Strava's [authentication documentation](https://developers.strava.com/docs/authentication/)
allows this loopback redirect; its [setup guide](https://developers.strava.com/docs/getting-started/)
describes the host-only callback-domain field.

Start the disposable accepted-history review copy:

```bash
.venv/bin/python -m rideworks --data-dir local_data/p2-05-review serve --port 8771
```

Open **http://127.0.0.1:8771/settings**. Settings shows only Configured / Missing
for credentials. Choose **Connect Strava**, authorize the Owner's account and
grant `activity:read_all`, then choose **Sync now**. The callback returns to a clean
Settings URL. New/enriched/unchanged counts, material exceptions, rebuild needs
and last successful sync time are shown compactly. Open Activities to see updates
immediately, with valid API UTC `Z` dates sorted and displayed under the accepted
browser-local date policy. A successful sync that creates Activities offers
**View Activities** back to the normal newest-first browser. Sync is manual; it does not run continuously. **Disconnect** removes
local authorization while retaining activity history and attempts remote revocation.

Settings actions use POST, a random one-use action nonce and same-origin checks;
controls disable during submission and the store lock rejects overlapping operations.
OAuth state expires after three minutes and is one-use. After restart, token/checkpoint
state and the aggregate display result persist; an interrupted authorization requires
Connect again. The private 0600 `.strava-settings.json` contains derived display counts
and an attention flag only. The checkpoint is authoritative; stale display counts are
omitted if a CLI sync advances it.

The web and CLI use the same code exchange, scope/athlete checks, token files and
sync/disconnect functions. Tokens are private (0600), excluded from Store inspection
and browser output. Refresh within an hour of expiry atomically retains the newest
refresh token before further requests, including when a later sync page fails.
Invalid/revoked authorization clears unusable local tokens and Settings offers Reconnect.

Secondary CLI maintenance/recovery commands remain supported:

```bash
.venv/bin/python -m rideworks --data-dir local_data/p2-05-review strava-connect
.venv/bin/python -m rideworks --data-dir local_data/p2-05-review sync-strava
.venv/bin/python -m rideworks --data-dir local_data/p2-05-review strava-disconnect
```

The CLI connect command opens a temporary loopback callback on port 8772 by default
(`--callback-port` changes it), waits up to three minutes, and emits aggregate JSON.
The CLI always uses loopback, independently of `PUBLIC_ORIGIN`. Strava explicitly
permits localhost/127.0.0.1 redirects; configured LAN browser callbacks still need
provider callback-domain acceptance.

Sync is explicit and sequential. The initial `after` is midnight UTC on the
latest stored export calendar day, minus **three days**. This is a conservative
calendar overlap for offset-unknown export dates. Later `after` values use the
last successful request cutoff minus three days. `before` is the current sync's
start time; that cutoff becomes the checkpoint only after observations commit.
Missing/invalid boundaries stop without a historical fallback. Normal sync uses `GET /api/v3/athlete/activities`, with 100 items per page and a
20-page safety bound. Empty/short pages finish; size/shape/rate/auth/network
failures leave observations and checkpoint unchanged. Tokens may legitimately
rotate before a failed sync. Reports contain aggregate counts and rate headers.

Existing stores need an explicit one-time refresh to acquire Strava Relative Effort
scores for already-associated recent rides. Restarting the app does not populate
them, and ordinary forward sync does not fill older stored rides. Use the same
data directory as the running app:

```bash
.venv/bin/python -m rideworks --data-dir '<same-data-dir>' refresh-strava-effort
```

The refresh requests at most 30 cycling
summaries from the last 60 days, skips responses with non-score changes, reports
aggregate counts, and does not advance the forward-sync checkpoint. It converges
Performance and Power Curve caches after updating summaries. This is separate
from modeled training stress; unavailable scores remain unavailable. Future rides
continue to receive scores through the existing manually initiated `sync-strava`.

API observations retain only the documented allowlist, retrieval timestamp,
mapping version and source association. Identical observations reuse the Source;
changed observations retain previous evidence with an explicit current pointer.
Established Strava IDs enrich the same Activity. Otherwise, a unique local
candidate must agree on absolute start exactly, compatible classification,
elapsed duration within one second and distance within one metre when both
provide it. Title alone never associates. Ambiguous/conflicting local matches
create a new API-backed Activity; conflicting established identities stop.

Current API title/type evidence is visible and attributable; export titles remain
inspectable. API-only review uses stream evidence when available; summary-only Activities stay thin. FIT summaries/native streams remain unchanged. API summary watts never become sample power. Sync now runs metadata → bounded stream enrichment → Performance freshness → atomic rebuild only if pending. The web and CLI share this orchestration; source files are never reparsed or reimported.

Successful ordinary sync leaves Performance current with no second rebuild click.
A policy migration also requires convergence, even when Strava returns unchanged
metadata. If recalculation fails, synchronized evidence/checkpoint and prior
Performance rows remain intact. **Performance update incomplete** appears only
while unresolved missing/stale/policy-outdated results remain, with **Retry
Performance update** as recovery. A later Sync now retries while pending remains;
current ineligible rows (including HR-only rides) do not keep the banner visible.
The action uses the same POST/nonce/origin checks and atomic rebuild as the CLI.

Restart the server, confirm Settings still shows Connected, and choose Sync now again
to verify overlap idempotence. Manual
overlap cannot promise detection of arbitrary old edits, deletes or back-dated
uploads. Absence from a list never implies deletion. Webhooks must be revisited
before unattended/public integration; this implementation has no polling loop.

```bash
.venv/bin/python -m rideworks --data-dir local_data/p2-05-review strava-disconnect
```

Disconnect attempts `POST /oauth/revoke` with client Basic authentication and
then removes local tokens even if remote revocation/credentials are unavailable.
It retains durable activity history. Current Strava retention/deletion policy
conflicts with the Owner's accepted durable-history decision; see the documented
policy boundary and acceptance limits in `reports/P2-05/verification.md`.

Reproducible synthetic acceptance (fake HTTP only; use a fresh synthetic directory):

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_strava.py'
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/prepare_rideworks_strava_review.py \
  --data-dir '<accepted-history-copy>' --synthetic-dir '<new-synthetic-directory>'
.venv/bin/python -m rideworks --data-dir '<synthetic-directory>' serve --port 8773
.venv/bin/python tools/verify_rideworks_strava_ui.py --port 8773 --session rideworks-p2-05
```

Open the managed Chromium session before the last command. Private synthetic
routes and screenshots remain under ignored `output/playwright/`. Synthetic
success is separate from real authorization/sync acceptance.
Screenshots and this file stay local/ignored. The verifier emits aggregate JSON
and independently checks every eligible prior baseline without a production
selector oracle or native stream reads, then verifies persisted history/restart.

## Strava stream review (STRAVA-004)

Normal **Sync now** also fetches `time,watts,heartrate,cadence,moving` sequentially
for recent API-only cycling Activities that lack usable stream evidence. It
reuses usable cached observations. Optional missing signals stay missing;
stream failures leave successful metadata/checkpoint changes intact and are
shown separately, with retry on a later manual sync. Rate/auth failures stop
further stream requests without busy retry. The existing private token state
and atomic refresh logic serve both metadata and streams.

Stream Sources retain exact returned order/values, resolution, series type,
original size, retrieval time, requested keys, mapping version and related API
summary Source. Identical observations are reused; changed observations remain
inspectable. These are separate from FIT/native records and Performance inputs.
The stream JSON limit is 16 MiB (five arrays for long rides), while metadata/token
responses retain their 2 MiB limit. Both use fixed HTTPS endpoints, redirect
rejection and a 20-second timeout. No location streams are requested or retained.

API-only review charts use returned offsets directly, with power/HR where
available. Missing values and gaps over one second break paths; no intermediate
samples are invented. Absolute inspection time explicitly maps the related
summary start_date plus an original offset. Array length/sampling metadata must
support pairing with time; ambiguous or duplicate/backward timing remains thin
with an explanation. Summary average watts never substitute for a series.
Source details distinguish stream observations from summary metadata. Supported
FIT-backed review keeps its existing native graph and best-20; API streams are
additional provenance only when file-backed power exists. Performance v2 uses API fallback only under the Owner-approved quality/precedence rules; automatic post-sync convergence makes eligible results current.

Stream-backed API-only rides use the normal Activity Review hierarchy: four
summary cards, power/HR chart, ride-local Best 20-minute power, and Ride summary.
Cards and Ride summary retain current Strava API summary evidence; supplied
averages are not recalculated from the stream. The local best-20 is explicitly
RideWorks-calculated from Strava API stream evidence. It requires 1,200 complete
power samples at exact consecutive one-second returned offsets, counts zeros,
and rejects windows crossing gaps or missing power. Raw maximum wins, exact ties
choose the earliest window, and displayed watts round half up. No qualifying
window (including HR-only streams) shows Unavailable with a reason. Returned-offset
bounds and calculation/source details stay inspectable. The same candidate result may enter Performance and exact prior-six-week context when v2 eligibility passes. Otherwise the local panel gives its exclusion reason. Rendering the review is read-only; only rebuild/convergence persists Performance.

The task's bounded initial catch-up covered the seven known P2-05 API-only rides;
it did not fetch streams across the historical archive. Stage A independently
compared four overlap rides with FIT first. See
`reports/STRAVA-004/verification.md` for the evidence and limits.


## Home dashboard and annual mileage goal (P3-01)

Home at `/` summarizes cycling mileage and current Performance. Activities lives
at `/activities`; Activity Review URLs remain `/activities/<id>`. The brand link
opens Home. Old root browser-filter bookmarks redirect to the matching
`/activities` query.

Set, update or clear the current rider-local year's **Annual cycling mileage
goal** in Settings. Targets are explicitly in miles, finite and positive, at
most 100,000 mi. There is no default target and no generic goal engine. Schema 7
adds only year, target miles and update time; previous-year targets remain
separate. Goal changes use the existing POST/origin/action-nonce protections and
an atomic write. A failed write preserves the prior target.

Virtual Ride and outdoor Ride mileage both count. Home uses the accepted
presentation distance: understood file/session or single-TCX-lap distance first,
then current API summary distance. Unspecified CSV distance units are excluded;
known zero remains zero. Missing distance/date and source contribution counts
are inspectable in Mileage evidence & calendar boundaries.

Home defaults to `America/Los_Angeles`; explicit `home_tz` and Settings `tz`
overrides remain supported without browser redirects. YTD includes January
1 through the current instant. Recent Mileage combines This Week (actual miles
since local Monday) and Last 7 Days (today and the six preceding local dates),
including the neutral comparison with the preceding seven days. The dashboard
has three summary cards; mileage values sit side by side on desktop and stack
on phone. Annual goal information stays in Mileage Progress.
Supported source dates with unknown timezone keep their source date.

Annual goal information lives only in Mileage Progress. Completed Monday–Sunday
bars show actual miles. The outlined current bar shows actual Monday-through-today
mileage and matches This Week Miles. The green line alone shows needed average
miles/week to December 31.
Each completed-week point uses cumulative actual YTD mileage through Sunday;
the current point uses YTD through today. Needed average is remaining goal miles
multiplied by seven, divided by remaining calendar days after that day. Goal met
means zero; no remaining time with miles remaining means Unavailable. Points
before the current goal year are unavailable; prior-year targets are not reused.
The same actual current-week total appears in the bar, top card and diagnostic payload.
Bars/points show an immediate miles-only tooltip on pointer enter/move or keyboard
focus, with immediate leave/blur dismissal and no native delayed SVG titles.

Percentage, remaining miles and linear calendar pace use unrounded totals and
the actual year length, including leap years. Needed average is arithmetic goal
progress, not a training recommendation. Recent Activities adds Avg Pwr from
understood file session `avg_power`, or understood single-lap TCX avg power,
then current API summary `average_watts`. CSV watts and raw stream averages are
not used. Selected values retain summary-source provenance in the payload.

The dashboard reuses current `virtual-power-evidence-v2` / `best-average-power-v1`
results, current 42-day best, latest eligible ride and exact prior-six-week
context. It recalculates cheap mileage presentation without loading raw streams
or materializing aggregates. Pending Performance retains the existing exception
banner and affected stale points stay suppressed. Normal sync updates Home on
reload through the unchanged shared automatic convergence path. Insights are
neutral calendar pace and accepted best-20 comparisons, with inspectable rules.

No FTP, Fitness/Training Load, readiness, workout planning, arbitrary-duration
power curve or AI surfaces are added. Owner approval and Analyst acceptance of
P3-01 remain separate from passing local verification.


## Training State (P4-02)

`/training-state` adds exact daily Fitness (42-day), Fatigue (7-day) and prior-day
Form. The browser-local calendar and selected date drive all three values,
7-day changes, daily rides and trailing 7-/42-day workload. Choose 6 weeks,
3 months, 12 months or all history; toggle lines independently. Click/touch the
chart or focus it and use arrows/Home/End; the date input inspects exact days.
The page includes rider-facing method help and per-ride source/calculation detail.
Home retains its existing content and adds a subordinate Training State link.

`rideworks.training_state.training_state(store, timezone_name, as_of=...)` reads
accepted source evidence. Qualified Performance-v2 power eligibility is consumed
without changing that policy. It selects calculated recorded power, FIT-only
small-gap estimates, adequately covering HR estimates ahead of partial power,
partial observed power, or unavailable. Dated FTP comes from the single SQLite history. There is no packaged CSV fallback; all entries have equal standing regardless of when they were added.
Manual dated changes update this database timeline and its revision; no CSV copy is updated.
FTP before the earliest history entry remains unknown. Historical settings use the accepted
America/Los_Angeles athlete calendar, independently of browser display timezone. Optional accepted dated HR contexts may be
passed as `hr_history`; otherwise the approved 58/158/143 retrospective assumptions
apply, with the fixed 1.92 coefficient. No generic athlete profile engine is added.

Schema 8 adds a replaceable per-ride calculation cache only. Source/extraction,
API stream, FTP source and parameter signatures automatically invalidate it after
imports, sync, re-extraction or accepted settings changes. Daily models recompute
from unrounded per-ride results. The initial uncached full-history calculation can
take several seconds; later reads load cached results. No source rows/originals or
Performance results are changed. Unscored evidence remains unavailable even though
its numerical model contribution is zero; no-record days are not asserted rest.

Observed kJ uses valid native one-second power bins only. Power NP resets at timer
restarts and uses unpadded complete 30-second means. FIT correction uses the arriving
sample backward for eligible interior gaps <=15 seconds and total missing <=1%;
API gaps are never corrected. Whole-session labels require exact boundary/timer
proof and verified calculation coverage. Missing interior and verified boundary
time are distinguished; unverified timer envelopes are not claimed missing active
effort. HR streams need >=99% time coverage, adjacent measured intervals <=15 seconds,
and alignment to a traceable source duration within max(1 second, 1%). The native
endpoint time-weighted mean is an estimate; no samples are manufactured. Source
summaries may supply measured HR with compatible same-source active duration when
no HR stream exists. Defective HR streams are not bypassed using their summary.

Verification tools accept private store paths; see `reports/P4-02/verification.md`.
The Owner-approved Elevate reference is used only by the external comparison tool,
never by the application, as calculation inputs, or as an initial seed.

## Rolling Training Advisor (P5-01)

Home, Plan and Activity Review share the current rider-local next recommendation.
Before a ride, that can be today. After any cycling ride is recorded today, the
primary recommendation advances to the first future date; completed today stays
separate. Historic Activity Review labels this live suggestion **Current next
ride**, without reconstructing an old plan. Plan extends through three upcoming
hard recommendations, with hard milestones and all intervening daily targets.

Two hard sessions in seven dates is a soft preference. After two supported
recovery dates, the immediate quality opportunity may exceed it with an explicit
frequency exception; later projections favor two. Heavy-leg feedback keeps the
next ride light. Sync, actual rides and corrections recompute the plan on view;
projections never contribute stress to Training State. Only past no-record dates
covered by successful sync can count as assumed rest for planning.

Trusted observed Virtual Ride power and dated FTP suggest workout stimulus.
Explicit current Strava race metadata is source-reported, while a race title
alone stays uncertain with quick confirmation. Corrections retain original
measurements. **I plan to do this** records a separate pre-ride date-level intent;
without it, Activity Review says **No recorded intent**. It never silently accepts
a suggestion or assigns intent retrospectively.

Schema 9 planning records remain local. No Training State, Performance, FTP or
Strava access policy changes. See `reports/P5-01/review-followup.md` for JIT §10
verification, limitations, source-neutral screenshots and reproducibility.

## Power-duration curves (PC-01; pending acceptance)

Performance keeps **20-Minute History** as its default and adds **Power Curve**
with independent comparison periods. Activity Review has a Power Curve section
and jump link, defaulting to the selected ride's preceding 42 days, excluding
the ride itself and every activity at or after its start. Prior 12 months and
all earlier history are alternatives. These are observed maximal mean-power
curves in watts, with exact evaluated durations and contributing activity links.

Build the new, replaceable schema-10 profiles once from retained sources:

```bash
.venv/bin/python -m rideworks --data-dir /path/to/local/store rebuild-power-curves
```

Normal successful Strava sync updates changed profiles automatically without
additional API requests. After manual imports/reextraction, choose **Update power
curves** on Performance or rerun the command. Unchanged profiles are reused;
`--force` explicitly recomputes all profiles. Stale results remain unavailable.
Computation uses short per-ride read snapshots and an atomic publication step,
so it does not hold an archive-long SQLite write lock.

Hover, tap or focus the chart and use arrow keys to inspect exact computed
anchors. Enter opens the selected contributing activity; each readout also
has its own focusable link. Provenance includes exact watt sum/sample count,
window bounds, source identity and timer-quality limitations. Connected lines
are visual guides between anchors, not interpolated exact results.

The accepted Virtual Ride file/API precedence is retained. Short complete
windows may qualify without a best-20 value. Verified timer intervals keep
observed stop endpoints and cannot be stitched; unverified timers do not clip
valid recorded samples. Outdoor and summary/estimated watts cannot supply
these curves. Existing Performance, Training State and planning calculations
are preserved. See `reports/PC-01/implementation.md` for review evidence.


## Historical FTP (FTP-01)

The unreleased FTP-01 implementation stores effective date and positive integer watts in SQLite schema 11. Each value applies until the next entry. All entries share one timeline; there are no imported/supplemental classes. Intermediate insertion preserves existing dates and watts. History/revision signatures invalidate FTP-dependent caches; retained power measurements and saved Planning intents are unchanged.

A genuinely new store has empty valid history. An upgraded existing store reports that explicit FTP migration is needed until initialized. Do not start the new release against the live store before Owner-approved promotion. Schema setup is not bootstrap, and old code cannot read the new schema.

The explicit import command requires a target and both approved old-release source files:

```bash
python -m rideworks.ftp_history --target-dir /path/to/private-copy \
  --source /path/to/old-release/data/athlete/strava_ftp_history.csv \
  --mirror /path/to/old-release/rideworks/data/strava_ftp_history.csv
```

Input equality, known checksum and interval structure are validated before target construction. Entries and completion state commit together. Completed replay is a no-op even after intermediate insertion. No runtime page silently imports files. The retired root FTP CSV is never an input.

This branch stages removal of all three FTP CSVs and the obsolete loader; the active release's files remain available until the separate authorized cutover. Follow the [reviewable promotion/rollback runbook](../reports/FTP-01/promotion-runbook.md). Recovery restores matching code and database; never decrement the schema version or substitute an old rehearsal database for current production.
