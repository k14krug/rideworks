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

The screenshot supports a date-and-displayed-duration preview. A plain paste
of a few full rows is still needed to verify clipboard row structure and
whether it supplies any link targets. Retain the distinction between the
displayed Time value and an API-verified elapsed time until they can be
compared on a confirmed matching effort.

## Candidate handling for a subsequent brief

- For API rows, use the exact effort ID for idempotence within the authenticated
  athlete and validate segment and activity identity before saving or combining
  provenance. A verified Strava activity ID can link to a RideWorks ride when
  the local match is unique. Preserve validated efforts with a missing or
  ambiguous local match for later linkage.
- Keep a pasted row's provenance as Owner-supplied My Results. Preserve the
  original date meaning as a calendar date when the paste has no time zone.
  Only exact verified identities should drive automatic merges or ride links.
- For a paste with only a date and duration, preview possible overlap with
  saved API efforts and past paste batches. Equal date and duration can also
  describe distinct attempts. Show ambiguous candidates and let the Owner
  confirm a duplicate, keep a separate attempt, or skip the row. Protect
  against replay of the same reviewed batch while preserving repeated rows
  within it. Do not silently deduplicate overlapping batches on date and time.
- A subsequent brief can evaluate a bounded API route for segments that return
  results, with explicit coverage limits and retention terms. Finalize a
  paste importer brief only after checking the clipboard evidence. Keep
  the two paths distinguishable by provenance.

No app data or application code changed. Stop at HARD Analyst review after
the remaining sample is evaluated.

- [Strava List Segment Efforts](https://developers.strava.com/docs/reference/#api-SegmentEfforts)
- [Strava My Results help](https://support.strava.com/en-us/articles/15401900-how-do-i-view-my-segment-results-on-strava)
- [SEG-01 probe](../SEG-01/probe.md)
