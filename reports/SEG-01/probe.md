# SEG-01 Dev probe

The Owner supplied a canonical Strava segment link. The bounded probe used the
existing Dev athlete connection with an unexpired activity:read_all token. It
made two authenticated GET requests to documented Strava API endpoints.

| Request | Response |
| --- | --- |
| Segment detail for the selected segment | HTTP 404 |
| Connected athlete's segment effort list for the selected segment | HTTP 404 |

The probe could establish neither effort visibility nor a cause for the 404s.
An unavailable effort list cannot establish an empty history. Recent and older
efforts, exact elapsed time, local linkage, and retrieval beyond 30 entries
remain unverified. The probe made no further requests and wrote no ride data,
token changes, payloads, or private identifiers.

The API reference marks effort detail and listing as subscription required.
Access remains an open question for Analyst review. Separately, the proposed
durable history needs a retention decision under the current Strava API Policy,
particularly sections 5.5 and 6.2.

- [Strava segment effort API reference](https://developers.strava.com/docs/reference/#api-SegmentEfforts)
- [Strava API Policy](https://www.strava.com/legal/api_policy)

## Activity-effort follow-up

One authenticated activity-detail GET with `include_all_efforts=true` returned
HTTP 200 for the Owner's reference ride. The response contained ten efforts.
Exactly one matched the supplied effort ID with full 64-bit precision. It
belonged to the connected athlete and reference ride, its nested segment ID
matched the canonical link, and its elapsed time was a positive integer.
A read-only lookup of the Strava activity ID found one existing RideWorks ride.

The result establishes single-ride visibility and deterministic linkage. The
earlier effort-list HTTP 404 remains unresolved, so historical coverage and
retrieval beyond 30 entries remain unverified. No corrected-ID request was
needed. The probe retained no raw response, private identifiers, or elapsed
values. SEG-01 remains at the HARD Analyst access and coverage gate.

## Newer Zwift ride follow-up

One authenticated activity-detail GET with `include_all_efforts=true` returned
HTTP 200 and six efforts. Exactly one matched the supplied effort ID at full
64-bit precision. The effort belonged to the connected athlete and reference
ride, its nested segment ID matched the canonical link, and its elapsed time
was a positive integer. The activity ID matched exactly one RideWorks ride.

This repeats the older ride's single-effort visibility and deterministic
linkage. Historical effort-list coverage and routine Sync behavior remain
unverified. No raw response or private IDs were retained. Return to HARD
Analyst review.
