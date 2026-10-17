#!/usr/bin/env python3
"""Non-migrating SQLite inventory. Output contains private paths/identities; keep local."""
import argparse
from contextlib import closing
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import shutil
import tempfile


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def source_manifest(db):
    """Fingerprint the database and any SQLite sidecars without opening it."""
    paths = [db, Path(str(db)+'-wal'), Path(str(db)+'-shm'), Path(str(db)+'-journal')]
    result = {}
    for path in paths:
        if path.exists():
            stat = path.stat()
            result[path.name] = (stat.st_size, stat.st_mtime_ns, file_hash(path))
    return result


@contextmanager
def read_snapshot(db, *, wal):
    """Inspect a private copy; never open source WAL/SHM files through SQLite."""
    sidecars = [Path(str(db)+suffix) for suffix in ('-wal', '-shm', '-journal')]
    present = [path.exists() for path in sidecars]
    if present[2] or present[0] != present[1]:
        raise ValueError('SQLite sidecar state is unsupported or incomplete')
    before = source_manifest(db)
    if wal and not present[0]:
        # With no WAL/SHM files, immutable mode can safely read the checkpointed
        # main file and cannot create shared-memory sidecars.
        uri = db.as_uri() + '?mode=ro&immutable=1'
    elif wal and present[0]:
        uri = None  # Open only the private main/WAL copy below.
    elif not wal and not present[0]:
        uri = db.as_uri() + '?mode=ro'
    else:
        raise ValueError('SQLite journal mode and sidecars disagree')
    with tempfile.TemporaryDirectory(prefix='rideworks-inventory-') as temporary:
        snapshot_path = Path(temporary) / 'rideworks.sqlite3'
        if wal and present[0]:
            # Copy the exact main/WAL pair to private temporary storage and let
            # SQLite build temporary SHM there. Opening source WAL directly can
            # mutate its transient SHM lock bytes even in query-only mode.
            shutil.copyfile(db, snapshot_path)
            shutil.copyfile(sidecars[0], Path(str(snapshot_path)+'-wal'))
            uri = snapshot_path.as_uri()
        if source_manifest(db) != before:
            raise ValueError('Database or SQLite sidecars changed during read-only snapshot')
        with closing(sqlite3.connect(uri, uri=True, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA query_only=ON')
            connection.execute('PRAGMA temp_store=MEMORY')
            yield connection


def cache_metadata(connection, tables):
    """Fingerprint replaceable cached contents without publishing underlying evidence."""
    result = {}
    for table in ('performance_history','training_stress_cache','planning_classification_cache','power_curve_profiles'):
        if table in tables:
            rows = sorted([tuple(r) for r in connection.execute(f'SELECT * FROM "{table}"')],key=repr)
            columns = [r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')]
            result[table] = dict(rows=len(rows),content_sha256=digest(rows),columns=columns)
    return result


def inspect(root):
    """Inspect one immutable rollback/WAL snapshot without changing its source."""
    root = Path(root).resolve()
    db = root / 'rideworks.sqlite3'
    # Header bytes 18/19 indicate WAL even when sidecars are currently absent.
    with db.open('rb') as stream:
        header = stream.read(100)
    mode = header[18:20]
    if header[:16] != b'SQLite format 3\0' or mode not in (b'\x01\x01', b'\x02\x02'):
        raise ValueError('Unsupported SQLite format or journal mode')
    wal = mode == b'\x02\x02'
    before = source_manifest(db)
    result = dict(path=str(root), sidecars={name:(root/name).is_file() for name in
                  ('.strava-tokens.json', '.strava-settings.json')})
    with read_snapshot(db, wal=wal) as conn:
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
        result['cache_fingerprints'] = cache_metadata(conn, tables)
        result['identity_digests'] = {t:digest(v) for t,v in result['identities'].items()}
        result['state_digests'] = {t:digest(v) for t,v in result['state'].items()}
        conn.execute('ROLLBACK')
    after = source_manifest(db)
    result['database_metadata_unchanged'] = before == after
    result['journal_sidecars_after'] = [s for s in ('-wal','-shm','-journal') if Path(str(db)+s).exists()]
    result['journal_mode'] = 'wal' if wal else 'delete-or-rollback'
    if not result['database_metadata_unchanged']:
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
            result=dict(path=str(root.resolve()),inspection_error=type(error).__name__,private_reason=str(error))
        result['id']=f'S{index:02d}';results.append(result)
        print(f'{result["id"]}: inspected={"inspection_error" not in result}',flush=True)
    fd=os.open(a.private_output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(results,stream,indent=2)


if __name__ == '__main__':main()
