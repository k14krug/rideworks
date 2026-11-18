# SEG-02 — Validate bulk sources for watched-segment history

## Purpose and requirements used
[Product requirements](../PRODUCT_REQUIREMENTS.md), [Strava API reference](https://developers.strava.com/docs/reference/#api-SegmentEfforts), [Strava My Results help](https://support.strava.com/en-us/articles/15401900-how-do-i-view-my-segment-results-on-strava), and the SEG-01 per-ride evidence and durable-history decision. Find a way to import useful older results in batches without an archive-wide ride scan or requiring one effort link at a time. Tempus segment-wide access returned 404; that is not proof of empty history.

## Execution Control
**Allowed Invocation: `/TASK only`.** Start after SEG-01 Analyst and Owner gates clear and it is integrated. Use Dev only. HARD — Analyst after research; this brief does not authorize an importer, persistence of probe results as app data, merge, or deployment.

## Probe
1. For Hilly KOM, use the exact segment ID already saved in Owner Dev. If not available, report that; do not guess or substitute. With the existing connected athlete, make at most one documented subscription-required List Segment Efforts GET. Record sanitized status, count, date coverage, field availability (exact effort and activity IDs, date, elapsed time), and whether the requested limit may have capped it. Compare with Owner-supplied My Results evidence if available; otherwise mark coverage unknown. A 404 or other failure is not zero efforts. No retries, repeat Tempus calls, or undocumented pagination.
2. For Tempus and Titans Loop, inspect a small privately supplied sample copied by the Owner from Strava web My Results, ideally with an older row and one already saved. Do not automate signed-in page extraction. Assess whether the ordinary paste preserves dates and elapsed times unambiguously, how many rows are visible/copyable at once if the Owner can tell, and whether actual effort or activity links are preserved. Keep both checks independent: a missing sample does not block the API probe. No need to copy the full history.
3. Propose duplicate handling for repeated imports and overlap with saved API efforts. Use exact verified IDs for automatic ride linkage; if only date and time survive, describe how preview can flag possible duplicates without silently merging or attaching them. Distinguish user-imported Strava results from API-derived data. Do not infer a time zone or claim complete history from the sample.

## Outputs and limits
Sanitized report with evidence, missing inputs, and recommendation for a subsequent importer brief or stop. No raw pasted rows, IDs, links, payloads, or credentials in Git. No application code, production work, archive sweep, scraper, or changes to routine Sync or saved data. Stop at HARD — Analyst even if both probes succeed.
