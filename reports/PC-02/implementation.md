# PC-02 implementation verification

Activity Review uses a separately cached elapsed-time power profile. Recorded
zero, confirmed native timer pause, estimated single-second gap and unknown
power are kept distinct. Standard windows require 95% observed non-pause time.
A selected ride with 90–<95% full-ride coverage gets a separate unconnected
recorded-power minimum using only observed watt-seconds. It cannot enter a
historical envelope. Performance and Home retain the strict PC-01 profile.

## Numerical checks

`DEBUG=0 .venv/bin/python -m unittest discover -s tests` passed 657 tests.
`tests/test_elapsed_curve.py` includes an independent small brute-force oracle,
pause and single-hole examples, fractional and integer endpoints, coverage
boundaries, the API-only coverage reproduction, cache separation, historical
bounds, competing sources and interrupted rebuild retry. The output is synthetic.

On a disposable copy of retained data, the affected API-only ride has an elapsed
clock of 6,553 seconds. In that domain there are 6,177 observed seconds and 376
unknown seconds, no verified pause, and no interpolation in the fallback.
Independently summing only in-domain observed samples gives 596,058 watt-seconds:
596,058 / 6,553 = 90.95956050663818 W. Observed coverage is 94.26216999847398%.
The standard full-duration point is unavailable; the separate minimum rounds to
91 W. Diagnostic exact 5,400- and 6,000-second standard windows were ineligible.
The earlier zero-gap illustration was a diagnostic, not a required parity target;
the current fallback excludes all unobserved work, including the repairable second.
The strict 1,200-second profile remained 131,143 watt-seconds / 1,200 =
109.28583333333333 W, rounded to 109 W, before and after the rebuild.

## Rebuild and browser checks

A disposable local copy was used; no new API requests or source changes were made.
`DEBUG=0 .venv/bin/python -m rideworks --data-dir <private-copy> rebuild-power-curves`
computed 1,462 elapsed profiles in 60.680 s; an unchanged warm run reused 1,462
in 0.453 s (0.908 s total including strict-cache checks). A cached Activity Review
comparison took 0.765 s and one local HTTP request took 1.969 s. These timings
are a single local observation, not a deployment guarantee. A forced combined
rebuild took 102.043 s; hashes of records, sources, stream evidence, strict
profiles and Performance history remained equal. Database integrity and foreign
key checks passed on both the source store and the disposable copy.
After finalizing elapsed error reporting, a second forced elapsed-only rebuild
computed 1,462 profiles in 62.116 s and reproduced the elapsed profile payloads
exactly. The first forced comparison was not a valid elapsed parity check because
error reporting had changed between the initial and forced builds.

Chromium on the disposable copy displayed the distinct 1:49:13 minimum at
91 W with 94.3% coverage and 376 unrecorded seconds. End-key selection and
mobile touchscreen selection reached it. The 390- and 320-pixel layouts retained
the marker and comparison choices; the 320-pixel document had no horizontal
overflow. The 320-pixel chart and readout were visually inspected. Browser
console reported no errors. A second supported ride's ordinary full-duration
endpoint was inspected at its exact 3,620-second duration. The original rides
and screenshots remain private.

The 95% cutoff and 90% minimum floor are PC-02 policy, not claims of vendor
parity. Missing work can raise the full-ride average. Analyst and Owner review
remain required; this report is not task acceptance or deployment.
