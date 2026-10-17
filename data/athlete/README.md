# Historical FTP source retirement

FTP-01 uses one date-effective SQLite history. The initial 66 settings were transcribed from the Owner-supplied Strava FTP history screenshot on 2026-10-09, with approval to version the dated record. The screenshot remains private. Those CSVs are removed from this unreleased branch; live import and active-environment retirement require the separate Owner-authorized promotion described in the [FTP-01 runbook](../../reports/FTP-01/promotion-runbook.md).

All current entries have equal standing. A value applies from its date, inclusive, until the next date, exclusive; the last extends indefinitely. Dates before the earliest entry remain unknown. These are Owner-managed historical FTP values, not independently measured physiological thresholds. Import origin does not change display, permissions or calculations.

There is no packaged FTP dataset, default CSV fallback, archival replacement CSV or permanent embedded seed. New stores start with valid empty history; existing uninitialized stores require explicit bootstrap from the two approved old-release sources. Bootstrap validates both before opening its explicit target, imports atomically and records completion. Replay preserves later entries.

The historical P4-01 research utilities still accept explicit caller-supplied files for reproducing those old experiments. They are not current runtime readers or a way to populate the production timeline. Tests use generated synthetic data. Git history and old reports document the retired source; no new copy is retained here.
