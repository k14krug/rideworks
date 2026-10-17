# FTP-01 Gate 1 implementation and verification

Gate 1 implements one SQLite date/watts timeline, explicit validated bootstrap, durable initialization/replay state, intermediate insertion and shared FTP context across Training State, Planning, Home and Activity Review. There are no origin-based classes or duplicate original datasets. This is unreleased code; production has not been opened through the new Store.

## Verification actually performed

- `DEBUG=0 /home/kkrug/projects/rideworks/.venv/bin/python -m unittest discover -s tests`: 483 passed in 31.081 seconds (Astra implementation pass). After the final completed-history transaction wrapper, `DEBUG=0 PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -m unittest test_rideworks_ftp_history test_rideworks_planning test_rideworks_training_state`: 70 passed in 2.835 seconds. Distinct technical review follows.
- `tools/verify_ftp_history_private.py` ran the old code against a consistent read-only SQLite backup copied into private baseline storage, then the new code against a separately bootstrapped private working copy. Both fixed-clock/timezone model scenarios matched after normalizing only FTP storage metadata; six page renders succeeded. 24 non-cache tables and 1,422 original artifacts remained identical. Cold recomputation was 21.2 seconds; warm refresh 0.47 seconds. [Aggregate evidence](gate1-parity.json).
- `tools/verify_ftp_insertion_private.py` inserted a lower intermediate FTP on another private copy: all 66 prior rows retained, 67 total, inverse-square power stress verified, independent exponential convolution verified through subsequent days, HR candidates/work/performance unchanged, bootstrap replay and restart/cache agreement passed. [Aggregate evidence](gate1-insertion.json).
- Old code rejected schema 11 as expected. Restoring the baseline database/artifact copy and running the matching old code reproduced baseline models and preservation checks. [Aggregate recovery evidence](gate1-rollback.json). No schema downgrade was attempted.

## Reproduction

Run from the isolated task checkout. `OLD` is the unchanged release checkout, `PY` its Python environment, and `PRIVATE` an ignored private directory containing separate consistent database/artifact copies. Never substitute the production directory for a test target.

```bash
PY=/home/kkrug/projects/rideworks/.venv/bin/python
OLD=/home/kkrug/projects/rideworks
PRIVATE=local_data/ftp01
$PY tools/verify_ftp_history_private.py --code-root "$OLD" --data-dir "$PRIVATE/baseline" --protected-store "$OLD/data" --snapshot "$PRIVATE/baseline-models.json"
$PY -m rideworks.ftp_history --target-dir "$PRIVATE/working" --source data/athlete/strava_ftp_history.csv --mirror rideworks/data/strava_ftp_history.csv
$PY tools/verify_ftp_history_private.py --code-root . --data-dir "$PRIVATE/working" --protected-store "$OLD/data" --snapshot "$PRIVATE/baseline-models.json" --compare --report "$PRIVATE/gate1-parity.json"
$PY tools/verify_ftp_insertion_private.py --data-dir "$PRIVATE/insertion" --protected-store "$OLD/data" --source data/athlete/strava_ftp_history.csv --mirror rideworks/data/strava_ftp_history.csv --report "$PRIVATE/gate1-insertion.json"
$PY tools/verify_ftp_history_private.py --code-root "$OLD" --data-dir "$PRIVATE/rollback" --protected-store "$OLD/data" --snapshot "$PRIVATE/baseline-models.json" --compare --report "$PRIVATE/gate1-rollback.json"
```

The insertion copy starts from the migrated working copy; the rollback copy starts from the old baseline. All private snapshots and copies remain ignored. The original checkout and its approved CSV inputs remain available. Gate 2 retirement staging will change task-checkout source paths; use explicit old-release source paths for later rehearsal.

## Gate boundary

Gate 1 cannot advance until its distinct fresh-context Astra technical review is affirmative and ordinary findings are fixed and verified. Gate 3 remains the Owner's production authorization boundary; this evidence authorizes no production writes, deployment, active CSV removal or merge.
