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
