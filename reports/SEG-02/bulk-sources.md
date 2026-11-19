# SEG-02 bulk history source research

## Hilly KOM API probe

One exact Hilly KOM watch matched the connected athlete in the local Dev store.
One authenticated, documented List Segment Efforts GET requested 100 results
for the saved segment. It returned HTTP 200 with 100 rows. Python parsed the
identifiers as exact integers, without converting them to floating point.

| Observation | Result |
| --- | --- |
| Documented list requests | 1 |
| Rows at requested limit | 100 of 100 |
| Exact, unique effort IDs | 100 |
| Exact activity IDs | 100 |
| Rows matching the connected athlete and watched segment | 100 |
| Valid API dates | 100 |
| Positive integer elapsed times | 100 |
| Observed date coverage | 2018–2026, a 3,045-day span |

The response hit the requested limit. It demonstrates access and usable fields
for Hilly KOM but leaves total history coverage unknown. Independent Hilly KOM
My Results evidence was unavailable. The earlier Tempus result was HTTP 404;
the Hilly KOM success does not establish segment-wide access for Tempus.
The response was examined in memory and discarded. No further requests ran.

## Tempus My Results paste

The Owner supplied two activity-effort links. Both yielded exact activity and
effort IDs. A read-only Dev lookup found one exact saved effort match and a
unique local ride for each link, with no additional Strava request. This
demonstrates repeat detection for a saved ID and exact ride resolution when
those URLs are available. The links alone contain no date or elapsed time.

The Owner's screenshot shows 25 visible ranked rows in the All Time view.
Each shows a calendar date with an English month name and four-digit year,
and a separate Time column displaying minutes and seconds. The screenshot
shows no time of day or time zone. Dates appear as links, but their targets
are unavailable in the image. The view shows 25 rows at once in this example.
Total history and the number of rows that can be copied at once are unknown.

The Owner then provided two copied rows. Both preserve the calendar date and
displayed Time to the second without a time of day or time zone. Both date
links point to canonical activity URLs containing exact activity IDs. Neither
row carries a canonical effort URL, effort ID, or segment ID. Both activity IDs
mapped uniquely to local RideWorks rides through established Strava source
IDs. Neither had a saved effort for this segment in Dev, so equivalence of
the displayed Time and API elapsed time remains unverified. The earlier
exact saved-effort match involved the separate effort-link sample.

The copied representation contains Markdown table separators and a stray
icon marker in the Power field. Date, activity link, and Time remain
unambiguous in this sample. Treat the surrounding fields as optional and
ignore the athlete link for ride matching. Two rows were supplied as separate
table fragments. The 25 visible rows are evidence of what the page displays,
while how many rows survive one clipboard copy remains unknown.

## Candidate handling for a subsequent brief

- For API rows, use the exact effort ID for idempotence within the authenticated
  athlete and validate segment and activity identity before saving or combining
  provenance. A verified Strava activity ID can link to a RideWorks ride when
  the local match is unique. Preserve validated efforts with a missing or
  ambiguous local match for later linkage.
- Keep a pasted row's provenance as Owner-supplied My Results. Preserve the
  original date meaning as a calendar date when the paste has no time zone.
  Record the displayed duration separately from API-verified elapsed seconds.
  Require the Owner to select the watched segment for the batch because the
  pasted rows do not identify it. Link a ride automatically only when its
  canonical activity ID maps uniquely through local established Strava IDs.
  An activity ID alone cannot authorize an effort merge.
- For a paste with only a date and duration, preview possible overlap with
  saved API efforts and past paste batches. Equal date and duration can also
  describe distinct attempts, even on the same ride. Where an activity ID is
  available, narrow possible duplicates to the same watched segment and ride.
  Show candidates and let the Owner confirm a duplicate, keep a separate
  attempt, or skip the row. Protect against replay of the same reviewed batch
  while preserving repeated rows within it.
- A subsequent brief can evaluate a bounded API route for segments that return
  results, with explicit coverage limits and retention terms. For Tempus,
  recommend an Owner-reviewed paste importer starting with dates, displayed
  durations, and optional exact ride links. Keep the two paths
  distinguishable by provenance.

The bounded API probe and sample assessment are complete. No app data or
application code changed. Stop at HARD Analyst review before importer work.

- [Strava List Segment Efforts](https://developers.strava.com/docs/reference/#api-SegmentEfforts)
- [Strava My Results help](https://support.strava.com/en-us/articles/15401900-how-do-i-view-my-segment-results-on-strava)
- [SEG-01 probe](../SEG-01/probe.md)
