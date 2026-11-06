# RACE-01 implementation and synthetic verification

## Implementation

RideWorks accepts a PNG, JPEG or WebP race screenshot and discloses that
extraction sends it to OpenAI and incurs API charges. The server validates the
image, requests strict structured output, retains the original locally, and
stages the extracted rows for correction. Extraction does not create confirmed
race results or activities.

Review supports a screenshot display timezone, same-day activity candidates
with source context, conservative automatic suggestions, explicit activity
selection, skip/confirm, duplicate detection and explicit approval of changed
results. Confirmation is transactional and stores race-reported watts
separately from FIT and other activity measurements. An additive SQLite
migration links accepted results and their revision history to existing
activities and screenshot/model/prompt/schema provenance. Race Results and
Activity Review link to one another.

The default model is `gpt-4o-mini`, with a configurable model and upload limit.
Request construction uses the OpenAI Responses API image input and strict
JSON schema documented by OpenAI:
[images and vision](https://developers.openai.com/api/docs/guides/images-vision),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
and [model capabilities](https://developers.openai.com/api/docs/models/gpt-4o-mini).
Reported token usage and cost, when returned, are retained without assuming a
price. The original screenshot and extraction data remain in the private store.

## Verification

All verification used synthetic images, synthetic activities, and controlled
mock API responses. No personal screenshot or other personal activity data was
sent to OpenAI, and no live OpenAI request was made.

From the task worktree:

- `.venv/bin/python -m unittest discover -s tests -p test_race_results.py`:
  **14 tests passed**. Coverage includes strict request/schema construction,
  wrapped titles, group badges, signed/zero/missing score changes, watt-field
  distinctions, 100/101 row boundary, image types and failures, missing key,
  HTTP error and timeout, retained originals, HTML escaping, review correction,
  idempotence, changed-result approval, transaction rollback, preservation of
  FIT evidence, matching ambiguity/timezones, and migration rollback.
- `.venv/bin/python -m unittest discover -s tests`: **574 tests passed**.
- `.venv/bin/python -m compileall -q rideworks tools/preview_race_results.py`,
  `node --check tools/verify_race_results_browser.js`, and `git diff --check`
  passed.
- `tools/preview_race_results.py` and `tools/verify_race_results_browser.js`
  exercised **12 browser checks** with a generated 33-row synthetic image and
  three mocked extraction rows, at 1440 px and 390 px. The checks covered
  disclosure, upload, preview, editing, matching, confirmation, navigation,
  date sorting and mobile overflow. They do not measure OCR accuracy.

For a disposable browser rerun, create a new empty directory and start the
mock-only preview with
`.venv/bin/python tools/preview_race_results.py --data-dir <empty-directory> --port 18893`.
Open `http://127.0.0.1:18893/race-results` in Playwright and run
`tools/verify_race_results_browser.js` with the repository's `run-code`
workflow. Stop the preview after the check.

## Review boundary and limitations

The Analyst accepted Gate 1. The subsequent Owner-initiated live test exposed
incorrect average-watt values and date/time formats. The Analyst then
authorized a bounded correction.

## Owner-test correction

The revised versioned prompt explicitly specifies visible-row boundaries,
truncated titles, date/time conversion, the WATTS column, and score/change
semantics. The upload defaults to `America/Los_Angeles`, which the user may
change or clear. Review normalizes supported display dates and times without
changing the retained model response, warns about earlier extractions, and uses
a more compact layout. Old extracted watts are not silently corrected.

Local-only comparison of the Owner's prior response against the retained
screenshot found that, after format normalization, the first visible row
matched seven of eight fields; its average watts remained incorrect. All 11
rows' date/time format errors were resolved, and 10 of 11 had at least one
same-day activity candidate; one of those had multiple candidates. No race
result was confirmed during this comparison. These observations concern the
old prompt and do not establish the revised prompt's accuracy.

- `.venv/bin/python -m unittest discover -s tests -p test_race_results.py`:
  **18 tests passed**.
- `.venv/bin/python -m unittest discover -s tests`: **578 tests passed**.
- Synthetic browser checks verified the timezone default, editing, manual ID,
  candidate selection, explicit confirmation and mobile overflow. Three
  complete review rows fit at 1440 by 900 pixels without scrolling.
- `compileall`, `node --check tools/verify_race_results_browser.js`, and
  `git diff --check` passed.

At this point the revised prompt's real recognition accuracy and any
additional API cost were unverified. Only the Owner may initiate another live
extraction. The PR remains draft, and no production deployment is authorized.

## Second Owner-run extraction

The Owner subsequently initiated a second live extraction using the revised
prompt and supplied a separate reference transcription. Local comparison of
the 11 rows found 11/11 exact date, start-time and finish matches, 8/11 exact
group matches, 0/11 average-watt matches, 1/11 score matches, and 7/11 score
change matches. Event titles were not included in this count. These figures
describe the saved response compared with the supplied reference, not a
general model benchmark. The Owner also reported that candidate labels omit
dates and that near-time matches are not preselected. JIT section 12 requires
another stop because the real error rate remains high.

## Second Owner-test correction

The Analyst authorized the Owner's prompt verbatim, a 10-minute matching window
and marking a unique qualifying match for import, subject to the final Confirm
Import action. The new prompt and schema versions preserve the submitted text;
the schema separately describes the required `HH:MM` time format. The model
remains `gpt-4o-mini`. No new live request was made by the agent.

Candidate labels now show the local activity date and time, including a
manually selected activity outside the race date when its timestamp is
available. Automatic preselection requires a unique qualifying same-day,
absolute-time virtual ride within 10 minutes, a meaningful title-word overlap,
and unambiguous local times. Other candidates remain available for manual
review. Older prompt versions display a warning about potentially wrong watts
and scores.

Verification:

- The full Python suite passed: **580 tests**, including **20 race tests**.
- Exact prompt equality, time-window boundaries, ambiguous candidates, generic
  title words, daylight-saving ambiguity, candidate dates, and a selected
  outside-date activity were checked offline.
- One retained real response produced 11 dated, preselected candidate options
  locally. After restart, the newest saved response produced 10; its remaining
  candidate was 13 minutes apart, outside the approved 10-minute window. No
  confirmed results were written. This verifies matching, not extraction
  accuracy. Those earlier extracted values remain incorrect.
- Python compilation, browser-script syntax and `git diff --check` passed.

At this point the verbatim prompt's live accuracy was unverified. Only the
Owner may initiate another extraction. The PR remains draft and production
deployment is not authorized.

## Owner-run verbatim-prompt test

The Owner subsequently initiated a live extraction with prompt v3 and confirmed
11 results. Local comparison against the Owner-supplied reference found 10/11
confirmed average-watt values, 1/11 scores and 1/11 score changes matched.
The same counts apply to the model's returned rows. The Owner requested merge,
but JIT section 12 requires a stop for this high live error rate. No confirmed
records were changed by the agent. Accuracy and the disposition of the saved
results need Owner/Analyst review before merge or worktree removal.
