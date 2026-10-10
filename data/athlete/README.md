# Historical cycling FTP — owner-approved Strava record

The 66 date/value entries in [`strava_ftp_history.csv`](strava_ftp_history.csv) were transcribed from the rider's Strava **Functional Threshold Power** history screen, supplied by the Owner on 2026-10-09. The Owner **explicitly approved committing these FTP records to this public RideWorks repository** on 2026-10-09. This is a narrow exception to the normal local-only default for personal source data, not permission to commit raw activity files, databases, OAuth secrets, or other personal data.

## Meaning of fields

- `effective_from_date`: the exact calendar date shown by Strava for the corresponding FTP setting, in ISO `YYYY-MM-DD` form; **not** an inferred activity time or an observed API change timestamp.
- `ftp_watts`: the FTP value displayed by Strava for that date. It is an **historical Strava setting**, not independently validated laboratory-measured threshold power.
- `effective_until_date_exclusive`: the next entry's listed date, derived from chronological order. The last row is blank (open-ended pending a future confirmed update).

The Owner approved the interval convention: each FTP applies from its listed calendar date, inclusive, until the next listed date, exclusive. For dates **before 2019-07-18**, FTP is *unknown*, not zero and not 180 W. Duplicate values recorded on different dates (e.g., 194 W on 2020-01-02 and again on 2020-04-24) remain separate entries because the source contains distinct dated observations.

These are date-level observations. When an Activity falls on an FTP-change boundary and its timezone/calendar interpretation is uncertain, RideWorks must make the uncertainty explicit rather than inventing an exact timestamp.

## Scope and provenance

- Source: Owner-supplied screenshot of Strava's historical FTP UI, manually transcribed and structurally checked against the Owner-approved effective-interval CSV.
- Date coverage: **2019-07-18 through 2026-09-24**, 66 rows with distinct, increasing dates.
- The screenshot itself is **not** committed.
- This CSV is now **version-controlled source evidence for P4-01 research**, but merely committing it does **not** mean the values have been imported into the running RideWorks athlete-state store.
- The prior P4-01 census of *already retained* source evidence (one usable same-session cycling threshold) remains an accurate description of the old dataset. This is additional Owner-supplied evidence.
- Later additions or corrections should preserve their own provenance and effective-date semantics; do not silently overwrite the historical observations.
- P4-01 must still evaluate whole-session power timing/gap eligibility and missing/excluded outdoor load separately. Dated FTP does not make source power reliable or make absent watts equal zero.

**Product decision:** record/history source and interval interpretation accepted. **Model selection, production import/schema, and P4-02** remain subject to their own Owner review.

## P4-02 application calculation context

P4-02 packages a byte-identical copy of the approved CSV at
`rideworks/data/strava_ftp_history.csv`. The loader validates ISO dates, increasing
start dates, positive integer watts and contiguous inclusive/exclusive intervals;
the last interval must remain open. It validates content independently of record
count. The initial approved artifact's 66 rows are checked separately by tests.

An explicitly updated, approved dated record can be passed through
`ftp_history(source_path)` or `training_state(..., ftp_source=source_path)`.
This is a deliberate calculation input, without automatic discovery or a new
settings UI. The content digest participates in the per-ride cache signature,
so a supplied record update recalculates derived stress without changing code.
New observations still require their own approved provenance. Elevate FTP
settings never populate this context.
