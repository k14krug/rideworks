# PC-04 implementation verification

Power Curve period comparisons now consume the same cached standard elapsed
profiles and shared period aggregation as Activity Review. The selected-ride
minimum and off-grid ride endpoints do not enter period bests. The existing
strict consumers, elapsed calculation rules, cache format and source admission
remain unchanged. The pinned inspector describes elapsed work, coverage,
timing buckets and source evidence.

## Verification

- `env -u DEBUG .venv/bin/python -m unittest discover -s tests`: **662 passed**.
  Focused elapsed tests passed **20** and focused power-curve tests **24**.
  The first sandboxed run could not open local sockets; a run with an inherited
  invalid `DEBUG` value also caused subprocess errors. The final run used local
  networking and removed that unrelated environment value.
- Synthetic elapsed tests cover an independently checked winner, unrounded
  values and tie ordering, equal period evidence across both views, period
  boundaries/timezones, partial and fully stale caches, strict versus elapsed
  windows, excluded minimum/off-grid endpoints, and a standard window with
  pause, estimate and unknown seconds. Strict history and Activity Review
  regression checks passed.
- A disposable copy of retained Dev data was examined at one fixed as-of time,
  without rebuilding or fetching data. Both methods included the selected ride;
  the elapsed period had a longer supported final anchor than the former strict
  period, and the selected ride won three elapsed anchors. Its individual
  recorded-power minimum remained outside the period. The complete selected
  Activity Review comparison payload matched the pre-change implementation.
  Specific personal values and identities were reported privately to the Owner.
- `tools/verify_pc04_presentation_browser.js` passed **35 Chromium assertions**
  covering exact delta and links, missing anchors without bridging, evidence,
  empty/partial periods, square-root mapping, and narrow-width containment.
  Retained-data Chromium checks covered both selectors, pinning, keyboard,
  disclosure and native links at desktop, 390 px and 320 px; no overflow was
  found. Touch pin, link, details and scroll passed. A deliberately stale
  profile on the disposable copy showed the update action and partial curve;
  its signature was restored after the check.
- No schema, strict calculation, production data, production deployment or
  Strava fetch was changed. Private activity data and screenshots are omitted.

This handoff stops at HARD — Analyst Gate 1; Owner running-Dev review follows
Analyst clearance. No merge or production deployment is authorized.
