# RE-01 — Relative Effort (development prototype)

Status: **Implemented on dev for rider review; not production accepted.**
Owner direction: October 2026, RideWorks project conversation. The 42-day window,
five colored text labels, load-first treatment of intensity, Ride Details card,
and Activities column were explicitly approved in discussion.

## Purpose

Show how demanding each cycling workout was **relative to this rider's
historical rides**, without relying on reported RPE, adding a second stress
model, changing Fitness/Fatigue, or claiming a medical or readiness assessment.

## Versioned first-pass rule (`relative-effort-v1`)

- Compare each dated cycling ride with the **previous 42 rider-calendar days**
  (`America/Los_Angeles`), including day minus 42 and excluding the ride's own
  day, later rides and future activities. This fixes a historical comparison
  window for list and detail regardless of when the page is opened.
- Use RideWorks' **selected modeled training stress**, preserving the chosen
  measured/estimated source and dated FTP. Use **the duration supporting that
  selected stress** (recorded/corrected power interval seconds, estimated
  session active seconds, or supported HR duration) to derive
  `stress points × 3600 / active seconds` as an *intensity proxy*.
- Unavailable, partial-only, unsupported active duration, uncertain timezone or
  fewer than **six** previous eligible workouts: **Not rated**, with reason.
  A legitimate scored zero remains zero.
- Compare total stress (Training load) and stress/hour (Intensity) independently
  against the same qualifying prior rides using empirical midrank percentiles:
  `(count strictly lower + 0.5 × count equal) / n`.
- Bands for percentiles `[0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1]`:
  Very Light, Light, Moderate, High, Very High. These are **within-rider
  history percentiles**, not physiological severity thresholds.
- Overall starts with Load's band. If Intensity is at least **two bands
  higher**, increase Overall by **one band**, capped at Very High.
  The rule is an interpretable new RideWorks heuristic, **not an established
  sports-science formula**. Do not average load and intensity percentiles;
  load itself already incorporates intensity.
- Share the exact same result between the Activity Review sidebar (under Ride
  Summary) and the Activities list. The list shows one compact label; the card
  shows Load/Intensity separately, 42-day population, and method details.

## Color and accessibility

Very Light: teal green; Light: green; Moderate: blue; High: amber; Very High:
muted red. Text is always displayed with a colored dot, never color alone.
Unrated is neutral gray.

## Provenance and limitations

This is a **presentation-layer** comparison built from the current versioned
Training State results. Source data, cache signatures, FTP history, Performance,
Planning, and modeled Fitness/Fatigue do not change.

Selected power stress and selected HR stress are different approximations of
training load; dividing each by duration supplies an understandable proxy for
intensity but does **not** establish identical physiological meaning. A short
hard workout may move up one overall band when intensity is exceptional, while
long low-intensity endurance work can remain Very High through accumulated load.
Scores can be recalculated if past source evidence, dated athlete state, or model
methods are corrected.

There are no private RideWorks activities in this project execution environment.
Thus the thresholds and intensity/load behavior remain **provisional pending
real-rider calibration**: sample low-load recovery rides, long Z2 rides, short
VO2 work, race efforts, source-estimated HR rides and rides with unavailable
or partial-only stress. Examine counts and scores, not just final colors.
Automated synthetic tests and browser verification scripts are included, but
the live automated suite and actual responsive screenshots must be run in
the development environment before proposing promotion to main.
