#!/usr/bin/env python3
"""Non-migrating SQLite inventory. Output contains private paths/identities; keep local."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def inspect(root):
    """Keep normal SQLite locking; refuse WAL rather than mutate shared-memory files."""
    root = Path(root).resolve()
    db = root / 'rideworks.sqlite3'
    # Header bytes 18/19 indicate WAL even when sidecars are currently absent.
    with db.open('rb') as stream:
        header = stream.read(100)
    if header[:16] != b'SQLite format 3\0' or header[18:20] != b'\x01\x01':
        raise ValueError('Unsupported/WAL journal mode; safe read-only route needs review')
    if any(Path(str(db)+suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('Journal sidecar present; safe read-only route needs review')
    before = (db.stat().st_size, db.stat().st_mtime_ns)
    result = dict(path=str(root), sidecars={name:(root/name).is_file() for name in
                  ('.strava-tokens.json', '.strava-settings.json')})
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro', uri=True, isolation_level=None)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.execute('PRAGMA temp_store=MEMORY')
        conn.execute('BEGIN')
        result['schema'] = conn.execute('PRAGMA user_version').fetchone()[0]
        result['integrity'] = [r[0] for r in conn.execute('PRAGMA integrity_check')]
        result['foreign_key_errors'] = [tuple(r) for r in conn.execute('PRAGMA foreign_key_check')]
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        result['counts'] = {t:conn.execute('SELECT COUNT(*) FROM "'+t.replace('"','""')+'"').fetchone()[0] for t in tables}
        result['identities'] = {}
        for table, key in [('activities','activity_id'),('sources','sha256'),('strava_export_sources','external_id'),
                           ('strava_api_activities','external_id'),('strava_api_sources','observation_sha256'),
                           ('strava_stream_sources','observation_sha256')]:
            if table in tables:
                result['identities'][table] = sorted(str(r[0]) for r in conn.execute(f'SELECT "{key}" FROM "{table}"'))
        result['state'] = {}
        for table in ('annual_mileage_goals','planning_feedback','planning_classifications','planning_intents','strava_sync_state'):
            if table in tables:
                rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]
                result['state'][table] = sorted(rows,key=lambda r:json.dumps(r,sort_keys=True))
        result['latest'] = {}
        for table, column in [('activities','created_at'),('sessions','start_time'),('strava_api_sources','retrieved_at')]:
            if table in tables:
                result['latest'][table] = conn.execute(f'SELECT MAX("{column}") FROM "{table}"').fetchone()[0]
        if 'strava_api_sources' in tables:
            result['latest']['api_start'] = conn.execute("SELECT MAX(json_extract(evidence_json,'$.start_date')) FROM strava_api_sources").fetchone()[0]
        refs = []
        for table in ('sources','export_snapshots'):
            if table in tables:
                refs.extend(tuple(r) for r in conn.execute(f'SELECT stored_path,sha256,byte_size FROM "{table}"'))
        result['artifacts'] = []
        for relative, expected, size in refs:
            path = (root/relative).resolve()
            if not path.is_file():
                result['artifacts'].append(dict(path=relative,matches=False,missing=True))
                continue
            actual = file_hash(path)
            result['artifacts'].append(dict(path=relative,resolved_path=str(path),sha256=actual,size=path.stat().st_size,
                                            external_to_store=not path.is_relative_to(root),
                                            matches=actual==expected and path.stat().st_size==size))
        result['original_files'] = sum(p.is_file() for p in (root/'originals').rglob('*'))
        result['identity_digests'] = {t:digest(v) for t,v in result['identities'].items()}
        result['state_digests'] = {t:digest(v) for t,v in result['state'].items()}
        conn.execute('ROLLBACK')
    result['database_metadata_unchanged'] = before == (db.stat().st_size, db.stat().st_mtime_ns)
    result['journal_sidecars_after'] = [s for s in ('-wal','-shm','-journal') if Path(str(db)+s).exists()]
    if not result['database_metadata_unchanged'] or result['journal_sidecars_after']:
        raise ValueError('Store changed during inventory; report concurrent writer and retry safely')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,action='append',required=True)
    p.add_argument('--private-output',type=Path,required=True)
    a=p.parse_args()
    # Explicit output only; never read OAuth/settings contents, never use Store().
    if a.private_output.exists():p.error('Use a new private output file')
    results=[]
    for index,root in enumerate(a.data_dir,1):
        try:result=inspect(root)
        except (OSError, sqlite3.Error, ValueError) as error:
            result=dict(path=str(root.resolve()),inspection_error=type(error).__name__)
        result['id']=f'S{index:02d}';results.append(result)
        print(f'{result["id"]}: inspected={"inspection_error" not in result}',flush=True)
    fd=os.open(a.private_output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(results,stream,indent=2)


if __name__ == '__main__':main()
