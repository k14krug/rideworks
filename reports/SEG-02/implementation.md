# SEG-02 history import implementation

Segments offers Import history for one watched segment at a time. Both methods
show a preview before a separate save. The preview is held in the server for
confirmation with a short-lived token. Preview and save share the existing
origin, action nonce, and operation protections.

The API method requests up to 100 efforts per read, with five reads per
preview. A capped response can be divided using documented local date bounds.
The two windows overlap by one second on either side of the split, and exact
effort IDs deduplicate that overlap. Responses with out-of-window or missing
local dates provide no evidence for a bounded window. Capped or failed
windows produce incomplete-history warnings. An HTTP 404 suggests pasting
My Results, and authorization and rate failures stop further reads. Save
preserves existing API attempts and uses verified exact identities.

Paste accepts the demonstrated linked Markdown cells and unambiguous
tabular text. It stores a calendar day and displayed seconds separately from
API elapsed time. Exact established activity IDs link to a local ride only
when unique. The normalized batch key ignores formatting, rank, unused
columns, and row order while preserving identical-row multiplicity.
Uncertain overlaps are grouped and skipped by default. The Owner can
keep a separate attempt or confirm an existing match. After Sync supplies
an exact effort, the Segments screen can show an eligible possible match
for confirmation. A confirmed API and paste pair is displayed once with
both sources. Home and Activities still count each watched segment once
per ride.

## Verification

- The full Python suite passed 683 tests with
  `env -u DEBUG .venv/bin/python -m unittest discover -s tests`.
  Six focused tests covered a 140-effort API result, boundary overlap,
  the five-read budget, an invalid bounded response, HTTP 404 and 429,
  multiple paste fragments, a 27-row batch, malformed rows, replay and
  overlapping batches, separate identical attempts, unique and missing
  local links, and later Sync followed by explicit match confirmation.
- Controlled Chromium on disposable Dev data exercised API preview and
  save at 1440 px, and paste preview, default overlap skip, and valid-row
  save at 390 px. Both Home and Activities opened filtered history at both
  widths without overflow. Preview was verified before saving.
- A live Hilly KOM preview used the existing Dev OAuth path and a read-only
  activity database. It made three list reads and validated 100 efforts.
  A bounded history request failed, so the preview warned of incomplete
  coverage. No efforts were saved in live Dev.
- Tempus verification used synthetic rows with the same clipboard structure.
  The two Owner-provided rows are not enough to establish the displayed
  total of 61 efforts. The comparison value of 33:43 appears in the sample
  and screenshot, but this check does not establish a complete imported
  history or equivalence to API elapsed time.

The implementation follows the Owner's durable-history decision in the brief.
Strava's retention restrictions still apply. [Strava API Policy](https://www.strava.com/legal/api_policy)

## Clipboard and saved-history review revision

The import form reads the HTML flavor of a browser copy when it contains
table rows. A detached, inert template supplies date and displayed-time text
and an exact activity link from the date cell when the link matches Strava's
canonical activity URL. The form places only normalized text into the
textarea and makes no requests to pasted URLs. Without usable table HTML,
the plain-text parser can group a rank/date line, optional metrics, and a
separate duration. Those rows can be saved by date and displayed time when
the clipboard contains no activity link.

Preview feedback, progress and save results appear in Import history. A
zero-row preview explains how to retry and retains the selected segment
and paste. Saved efforts show Date, Time, Source and Ride, with labels
repeated on narrow screens. Histories above eight efforts start collapsed.

- The full suite passed 685 tests. New cases cover the observed multiline
  shape, omitted optional metrics, ambiguity at row boundaries, and
  retaining the paste and selected watch when preview cannot proceed.
- Chromium used native Ctrl+C and Ctrl+V between a rendered, sanitized
  My Results table and the running Dev form on a disposable store. The
  clipboard carried both HTML and plain text. The preview found two
  readable rows and one uniquely matched local ride. A non-Strava URL did
  not become an activity link. A separate, text-only clipboard paste
  parsed and saved all three dates and displayed durations without links.
- The browser check confirmed visible progress at submission, actionable
  zero-row feedback, and fields contained by the import card at 1440 and
  390 px. It also saved two API efforts. The saved history grew from 102
  to 109 efforts, with the second watch still accessible when the first
  history was collapsed. Both browser fixtures were synthetic. The
  Owner's signed-in Strava clipboard and persistent Dev data were not used.

To repeat the browser check, start the disposable server from the repository
root. Run the following Playwright CLI commands from a second terminal,
using a Chromium-enabled Playwright CLI.

```sh
env -u DEBUG .venv/bin/python reports/SEG-02/verification/clipboard-dev.py

playwright-cli --session=seg02 open about:blank
playwright-cli --session=seg02 run-code "$(cat reports/SEG-02/verification/clipboard-browser.js)"
playwright-cli --session=seg02 close
```

Restart the disposable server before repeating the check so the saved
counts and API-preview response reset.
