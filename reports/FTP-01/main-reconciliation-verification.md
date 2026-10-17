# FTP-01 current-main reconciliation and verification

**Date:** 2026-10-16.
**Branch:** `task/ftp-01-implementation`.
**Reconciled head:** `94ea2036115d784344b016264ab3a18f84a4f277` (merge of implementation `4753c19ce11a3bb2ed24c42414297526d17a8b67` with refreshed main `c748ef90fc9a64959c2facb7eb7aa55683ef8ced`).
**Controlling JIT:** `docs/tasks/FTP-01.md` at the reconciled head is byte-identical to refreshed `origin/main`; blob `35cc923590b0641085f9c59bfb536f91f03cfe60`. It preserves the latest Owner prehistory requirement and separate Gate 4 HARD Owner control.

## Conflict reconciliation

Git reported content conflicts only in `STATUS.md` and `TASKS.md`. They were resolved to preserve the latest Owner-reviewed implementation/evidence and current lifecycle while recording Owner authorization to merge after checks. The JIT merged without conflict, and a direct diff against `origin/main` is empty. No application code, tests, package files or runtime behavior changed in `4753c19..94ea203`; the complete tree delta is `STATUS.md`, `TASKS.md`, and `docs/tasks/FTP-01.md`.

The source checkout at `/home/kkrug/projects/rideworks` was fast-forwarded from `92667ad` to `c748ef9` to refresh main, as requested. That fast-forward brought PR #42 documentation only; `rideworks/` application source is identical between the two commits. The running application process had started before that refresh. No PR #41 code was pulled into or deployed from the running checkout.

## Verification

The parent ran these checks after reconciliation:

```sh
env -u DEBUG PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -m unittest discover -s tests
# 494 tests passed
node --check rideworks/static/ftp.js
git diff --check
# both passed
npx --offline --yes --package @playwright/cli playwright-cli -s=ftp01merge open --browser chromium http://127.0.0.1:8879/performance/ftp
npx --offline --yes --package @playwright/cli playwright-cli -s=ftp01merge run-code --filename tools/verify_ftp_browser.js
# 107 assertions passed; 1,029 candidate rides; one trial insertion
```

Browser checks ran against a new disposable directory made from the isolated preview using Python's SQLite backup API and a copy of its original artifacts. The trial insertion modified that disposable copy only. The temporary server on port 8879 was stopped. The user's port-8875 preview and actual production Store were not used for browser mutations.

## Focused independent review

[Astra's main reconciliation review](astra-main-reconciliation-review.md) is an affirmative fresh-context PASS at `94ea203`. Astra verified the JIT blob against `origin/main`, inspected the three-file conflict-resolution diff and latest Owner instructions, and found no material implementation change. Astra's report distinguishes its own consistency checks from the parent-run 494-test and 107-browser results.

## Production boundary and current observations

Production remains untouched by this task. The read-only 2026-10-16 observation and proposed plan are recorded in [the promotion runbook](promotion-runbook.md): active process/launch method, resolved live database path, 1,444 current Activities (one more than the 1,443-Activity rehearsal), schema 10 with no FTP tables, current approved source checksums, and a private backup destination proposal. The current FTP CSVs and production data remain in place. The GitHub merge authorization does not authorize Gate 4 writes, deployment or active CSV removal.
