# Elevate Fitness Trend reference

The Owner copied this original Elevate Fitness Trend CSV into the RideWorks
repository and explicitly authorized committing this exact file on 2026-10-09
as a permanent external benchmark. The export filename records 2026-10-09 at
15:58:52; no timezone for that filename timestamp is established.

- File: `fitness_trend_export.2026.10.9-15.58.52.csv`
- Original byte size: **496,966**
- Original SHA-256: **407cc7ac2105d5d0c5c8ce4c90775adcb7733957157c2dad6aaa0af05f1ebfb1**
- 5,925 chronological daily rows, 2010-08-04 through 2026-10-23.
- The final **14 days, 2026-10-10 through 2026-10-23, are Elevate projections**;
  they are not completed activities or observed training. Comparisons use only
  completed dates through 2026-10-09.

Keep the original CSV byte-for-byte unchanged. This is a narrowly approved
privacy exception for this file, not blanket permission for other exports,
activity archives, screenshots, mockup HTML, databases or secrets.

Elevate exports selected stress, HR/power stress, modeled Fitness (`ctl`), Fatigue
(`atl`), start-of-day Form (`tsb`), vendor zones and athlete-setting descriptions.
The values are rounded vendor outputs. Activity coverage, selected methods,
recording treatment, initialization and athlete settings can differ from
RideWorks. The export itself does not establish the Elevate software version,
complete configuration or validity of historical assumptions. In particular,
**Elevate's FTP history was not maintained as authoritative rider history**.
RideWorks uses the approved `data/athlete/strava_ftp_history.csv` and its dated
intervals instead. Vendor zones and weight/settings are not adopted here.

Use this dataset only for external sanity comparison and inspection. Do not
import its scores as RideWorks source truth, use them as model seeds, package
them with production calculation inputs, or expect numerical vendor parity.
P4-02 compares independently calculated RideWorks outputs against completed
reference dates; detailed comparison artifacts stay local under the JIT.
