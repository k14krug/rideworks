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
